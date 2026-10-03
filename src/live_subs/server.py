import asyncio
import math
import os
import re
import secrets
import struct
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager, suppress
from pathlib import Path

import numpy as np
import webrtcvad
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .audio import FRAME_BYTES, FRAME_SECONDS, SAMPLE_RATE, Segmenter
from .pipeline import Pipeline
from .preferences import read_preferences, update_preferences


def token_at(directory: Path) -> str:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "token"
    if not path.exists():
        # Exclusive creation also protects simultaneous first starts.
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as f:
                f.write(secrets.token_urlsafe(32))
        except FileExistsError:
            pass
    return path.read_text().strip()


def create_app(directory: Path, engine_factory=None):
    token = token_at(directory)
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="local-metal")

    @asynccontextmanager
    async def lifespan(app):
        if engine_factory is None:
            from .engine import MLXEngine

            factory = lambda: MLXEngine(directory / "models.json")  # noqa: E731
        else:
            factory = engine_factory
        try:
            app.state.engine = await asyncio.get_running_loop().run_in_executor(executor, factory)
            yield
        finally:
            executor.shutdown(wait=True, cancel_futures=True)

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["127.0.0.1", "localhost", "testserver"],
    )
    app.state.busy = False

    @app.get("/health")
    async def health():
        return {
            "service": "tingqiao",
            "ready": True,
            "busy": app.state.busy,
            "local_only": True,
            "protocol": 1,
            "translation_control": True,
        }

    def authorize_preferences(request: Request):
        origin = request.headers.get("origin")
        if origin and not re.fullmatch(r"chrome-extension://[a-p]{32}", origin):
            raise HTTPException(403, "Extension origin required")
        if not secrets.compare_digest(request.headers.get("authorization", ""), f"Bearer {token}"):
            raise HTTPException(401, "Pairing required")

    @app.get("/preferences")
    async def preferences(request: Request):
        authorize_preferences(request)
        return read_preferences(directory)

    @app.post("/preferences/initialize")
    @app.patch("/preferences")
    async def save_preferences(request: Request):
        authorize_preferences(request)
        # A small fixed schema; reject oversized input before JSON parsing.
        body = await request.body()
        if len(body) > 1024:
            raise HTTPException(413, "Preferences too large")
        try:
            import json

            return update_preferences(
                directory, json.loads(body), initialize=request.method == "POST"
            )
        except (ValueError, TypeError) as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.websocket("/stream")
    async def stream(ws: WebSocket):
        origin = ws.headers.get("origin", "")
        if not re.fullmatch(r"chrome-extension://[a-p]{32}", origin):
            await ws.close(code=1008)
            return
        await ws.accept()
        owned = False
        worker = None
        send_lock = asyncio.Lock()

        async def send(payload):
            async with send_lock:
                await ws.send_json(payload)

        try:
            config = await asyncio.wait_for(ws.receive_json(), timeout=5)
            if not isinstance(config, dict) or not secrets.compare_digest(
                str(config.get("token", "")),
                token,
            ):
                await ws.close(code=1008, reason="配对码错误")
                return
            language = config.get("language", "en")
            display = config.get("display", "zh-en")
            translate = config.get("translate", True)
            if type(translate) is not bool:
                await ws.close(code=1008, reason="翻译开关必须是布尔值")
                return
            if language not in {"en", "ja", "auto"} or display not in {"zh-en", "source-zh"}:
                await ws.close(code=1008, reason="不支持的字幕配置")
                return
            if app.state.busy:
                await ws.close(code=1013, reason="已有一个直播正在生成字幕")
                return
            app.state.busy = owned = True
            vad = webrtcvad.Vad(2)
            segmenter = Segmenter(partial_frames=40 if config.get("partials", True) else 10000)
            pipeline = None
            await send({"type": "ready", "sample_rate": SAMPLE_RATE, "frame_ms": 20})
            while True:
                message = await asyncio.wait_for(ws.receive(), timeout=30)
                if message["type"] == "websocket.disconnect":
                    break
                if message.get("text") is not None:
                    import json

                    control = json.loads(message["text"])
                    if control.get("type") == "stop":
                        if pipeline:
                            for job in segmenter.flush():
                                await pipeline.submit(job)
                            pipeline.finish()
                            await asyncio.wait_for(worker, timeout=30)
                        else:
                            await send({"type": "done"})
                        break
                    if control.get("type") == "ping":
                        await send({"type": "pong"})
                        continue
                    raise ValueError("不支持的控制消息")
                data = message.get("bytes", b"")
                if len(data) != FRAME_BYTES + 8:
                    raise ValueError("音频帧格式错误，应为时间戳 + 20ms PCM16")
                captured_ms = struct.unpack_from("<d", data)[0]
                if not math.isfinite(captured_ms) or abs(time.time() * 1000 - captured_ms) > 10000:
                    raise ValueError("音频已落后超过 10 秒，请重新开始")
                if pipeline is None:
                    pipeline = Pipeline(
                        app.state.engine,
                        executor,
                        send,
                        language,
                        display,
                        captured_ms - FRAME_SECONDS * 1000,
                        translation_enabled=translate,
                    )
                    worker = asyncio.create_task(pipeline.run())
                frame = data[8:]
                samples = np.frombuffer(frame, dtype="<i2").astype(np.float32)
                rms = float(np.sqrt(np.mean(samples * samples)))
                speech = rms >= 100 and vad.is_speech(frame, SAMPLE_RATE)
                gaps_before = segmenter.gaps
                for job in segmenter.feed(frame, speech, (captured_ms - pipeline.epoch_ms) / 1000):
                    await pipeline.submit(job)
                if segmenter.gaps != gaps_before:
                    await send({"type": "notice", "message": "音频发生中断，已重新对齐时间轴"})
                if worker.done():
                    await worker
                    break
        except (WebSocketDisconnect, asyncio.CancelledError):
            pass
        except Exception as exc:
            with suppress(Exception):
                await send({"type": "error", "message": str(exc) or "连接超时，请重新开始"})
        finally:
            if worker and not worker.done():
                worker.cancel()
                with suppress(asyncio.CancelledError, Exception):
                    await worker
            if owned:
                app.state.busy = False
            with suppress(Exception):
                await ws.close()

    return app

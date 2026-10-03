import asyncio
import math
import time
from collections import Counter, deque
from collections.abc import Awaitable, Callable
from concurrent.futures import Executor

from .audio import AudioJob, Mailbox


class Pipeline:
    def __init__(
        self,
        engine,
        executor: Executor,
        send: Callable[[dict], Awaitable[None]],
        language: str,
        display: str,
        epoch_ms: float,
    ):
        self.engine = engine
        self.executor = executor
        self.send = send
        self.language = language
        self.display = display
        self.epoch_ms = epoch_ms
        self.mailbox = Mailbox()
        self.wakeup = asyncio.Event()
        self.finishing = False
        self.last_text: dict[int, str] = {}
        self.first_text = {}
        self.counts = Counter()
        self.samples = deque(maxlen=256)

    def metrics(self):
        result = {"counts": dict(self.counts), "sample_count": len(self.samples)}
        for key in ("first_text_ms", "first_zh_ms", "tail_ms", "queue_ms"):
            values = sorted(sample[key] for sample in self.samples)
            if values:
                result[key] = {
                    "p50": values[(len(values) - 1) // 2],
                    "p95": values[math.ceil(len(values) * 0.95) - 1],
                }
        return result

    async def submit(self, job: AudioJob):
        if job.final:
            self.counts["segments"] += 1
        dropped = self.mailbox.put(job)
        if dropped:
            self.counts["dropped"] += 1
            self.first_text.pop(dropped.id, None)
            await self.send(
                {
                    "type": "dropped",
                    "id": dropped.id,
                    "count": self.mailbox.dropped,
                    "metrics": self.metrics(),
                    "message": "推理跟不上直播，已跳过旧片段以追上当前音频；请关闭草稿或换小模型。",
                }
            )
        self.wakeup.set()

    def finish(self):
        self.finishing = True
        self.wakeup.set()

    async def run(self):
        loop = asyncio.get_running_loop()
        while True:
            await self.wakeup.wait()
            self.wakeup.clear()
            while (job := self.mailbox.pop()) is not None:
                queue_age = (time.monotonic() - job.queued_at) * 1000
                capture_age = time.time() * 1000 - (self.epoch_ms + job.end * 1000)
                if queue_age > 2500 or capture_age > 2500:
                    if job.final:
                        self.mailbox.dropped += 1
                        self.counts["dropped"] += 1
                        self.first_text.pop(job.id, None)
                        await self.send(
                            {
                                "type": "dropped",
                                "id": job.id,
                                "count": self.mailbox.dropped,
                                "metrics": self.metrics(),
                                "message": (
                                    "片段等待或音频延迟超过 2.5 秒，已跳过以追上直播；"
                                    "请关闭草稿或换小模型。"
                                ),
                            }
                        )
                    continue
                began = time.perf_counter()
                try:
                    recognition = await loop.run_in_executor(
                        self.executor,
                        self.engine.transcribe,
                        job.pcm,
                        self.language,
                    )
                    text, language = recognition
                    asr_ms = (time.perf_counter() - began) * 1000
                    # An obsolete partial must never overwrite a final or add GPU work.
                    if not job.final and job.id <= self.mailbox.finalized:
                        continue
                    if not text:
                        if job.final:
                            reason = getattr(recognition, "reason", None) or "empty"
                            self.counts[reason] += 1
                            self.first_text.pop(job.id, None)
                            labels = {
                                "repetition": "重复异常",
                                "low_confidence": "识别置信度低",
                                "silence": "未识别人声",
                                "empty": "无识别结果",
                            }
                            await self.send(
                                {
                                    "type": "rejected",
                                    "id": job.id,
                                    "reason": reason,
                                    "metrics": self.metrics(),
                                    "message": f"已跳过片段：{labels[reason]}",
                                }
                            )
                        continue
                    base = {
                        "id": job.id,
                        "source": text,
                        "language": language,
                        "final": job.final,
                        "display": self.display,
                        "speech_end_ms": self.epoch_ms + job.speech_end * 1000,
                        "speech_start_ms": self.epoch_ms
                        + (job.speech_start if job.speech_start is not None else job.start) * 1000,
                        "queue_ms": round(queue_age),
                        "asr_ms": round(asr_ms),
                    }
                    self.first_text.setdefault(
                        job.id, max(0, round(time.time() * 1000 - base["speech_start_ms"]))
                    )
                    base["first_text_ms"] = self.first_text[job.id]
                    if job.final or self.last_text.get(job.id) != text:
                        await self.send({"type": "transcript", **base})
                    self.last_text = {job.id: text}
                    if job.final:
                        began = time.perf_counter()
                        first_zh_ms = None

                        def chinese_ready(zh, base=base, text=text, language=language):
                            nonlocal first_zh_ms
                            first_zh_ms = max(
                                0, round(time.time() * 1000 - base["speech_start_ms"])
                            )
                            event = {
                                "type": "translation_progress",
                                **base,
                                "zh": zh,
                                "en": text if language == "en" else "",
                                "first_zh_ms": first_zh_ms,
                            }
                            # Send while the GPU thread continues generating English.
                            asyncio.run_coroutine_threadsafe(self.send(event), loop).result(
                                timeout=3
                            )

                        translation = await loop.run_in_executor(
                            self.executor,
                            self.engine.translate,
                            text,
                            language,
                            self.display,
                            chinese_ready,
                        )
                        if first_zh_ms is None:
                            first_zh_ms = max(
                                0, round(time.time() * 1000 - base["speech_start_ms"])
                            )
                        sample = {
                            "first_text_ms": base["first_text_ms"],
                            "first_zh_ms": first_zh_ms,
                            "queue_ms": round(queue_age),
                            "tail_ms": max(0, round(time.time() * 1000 - base["speech_end_ms"])),
                        }
                        self.samples.append(sample)
                        self.counts["translated"] += 1
                        self.first_text.pop(job.id, None)
                        await self.send(
                            {
                                "type": "translation",
                                **base,
                                **translation,
                                **sample,
                                "translation_ms": round((time.perf_counter() - began) * 1000),
                                "metrics": self.metrics(),
                            }
                        )
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    self.counts["errors"] += 1
                    self.first_text.pop(job.id, None)
                    await self.send(
                        {
                            "type": "error",
                            "id": job.id,
                            "message": str(exc),
                            "metrics": self.metrics(),
                        }
                    )
            if self.finishing:
                await self.send({"type": "done"})
                return

"""Real local models + actual paced WebSocket PCM; no mock inference.

Uses macOS TTS as reproducible smoke fixtures, not a claim about live-stream WER.
Server must already be running. Results retain full recognized text for review.
"""

import argparse
import asyncio
import json
import struct
import subprocess
import time
import wave
from pathlib import Path

import websockets

SENTENCES = [
    ("en", "Samantha", "The next meeting starts at three o'clock. Please bring your laptop."),
    ("ja", "Kyoko", "次の会議は三時に始まります。パソコンを持ってきてください。"),
]


def fixture(directory, language, voice, text):
    path = directory / f"{language}.wav"
    subprocess.run(
        [
            "say",
            "-v",
            voice,
            "-r",
            "175",
            "-o",
            str(path),
            "--file-format=WAVE",
            "--data-format=LEI16@16000",
            text,
        ],
        check=True,
    )
    with wave.open(str(path)) as audio:
        assert (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) == (1, 2, 16000)
        pcm = audio.readframes(audio.getnframes())
    return pcm + bytes(32000)


async def measure(token, language, pcm, partials, auto_language=False):
    events = []
    async with websockets.connect(
        "ws://127.0.0.1:18765/stream",
        origin="chrome-extension://" + "a" * 32,
    ) as ws:
        await ws.send(
            json.dumps(
                {
                    "token": token,
                    "language": "auto" if auto_language else language,
                    "display": "zh-en",
                    "partials": partials,
                }
            )
        )
        assert json.loads(await ws.recv())["type"] == "ready"
        began = time.perf_counter()
        capture_epoch = time.time() * 1000

        async def receive():
            async for raw in ws:
                event = json.loads(raw)
                event["received_after_ms"] = round((time.perf_counter() - began) * 1000)
                if "speech_end_ms" in event:
                    event["end_to_end_ms"] = round(time.time() * 1000 - event["speech_end_ms"])
                events.append(event)
                if event["type"] == "done":
                    return

        task = asyncio.create_task(receive())
        for index, offset in enumerate(range(0, len(pcm), 640)):
            await asyncio.sleep(max(0, began + (index + 1) * 0.02 - time.perf_counter()))
            await ws.send(
                struct.pack("<d", capture_epoch + (index + 1) * 20)
                + pcm[offset : offset + 640].ljust(640, b"\0")
            )
        await ws.send(json.dumps({"type": "stop"}))
        await asyncio.wait_for(task, 90)
    translations = [e for e in events if e["type"] == "translation"]
    if not translations or any(e["type"] in {"error", "dropped", "rejected"} for e in events):
        raise RuntimeError(f"真实模型测试失败: {events}")
    for event in translations:
        assert event["zh"].strip() and event["en"].strip()
    chinese = "".join(event["zh"] for event in translations)
    english = " ".join(event["en"] for event in translations).lower()
    assert "三点" in chinese or "3点" in chinese, "必须保留音频中的三点钟"
    assert "three" in english or "3" in english, "英文必须保留三点钟"
    assert "会议" in chinese, "必须译出真实语音中的会议，而不是返回非空占位符"
    assert "电脑" in chinese or "计算机" in chinese, "必须保留携带电脑的要求"
    assert "meeting" in english and ("computer" in english or "laptop" in english)
    assert "上午" not in chinese and "下午" not in chinese, "不能为未指明的钟点补充时段"
    import re

    assert not re.search(r"\b(?:am|pm)\b", english.replace(".", ""))
    return events


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-partials", action="store_true")
    parser.add_argument("--auto-language", action="store_true")
    args = parser.parse_args()
    directory = Path(".local/benchmark")
    await asyncio.to_thread(directory.mkdir, parents=True, exist_ok=True)
    token = (await asyncio.to_thread(Path(".local/token").read_text)).strip()
    result = {
        "fixture": "macOS synthesized speech, real MLX inference",
        "partials": not args.no_partials,
        "auto_language": args.auto_language,
        "runs": [],
    }
    for language, voice, text in SENTENCES:
        pcm = fixture(directory, language, voice, text)
        events = await measure(token, language, pcm, not args.no_partials, args.auto_language)
        result["runs"].append({"language": language, "expected_source": text, "events": events})
        print(json.dumps(result["runs"][-1], ensure_ascii=False, indent=2), flush=True)
    suffix = "no-partials" if args.no_partials else "partials"
    if args.auto_language:
        suffix += "-auto"
    (directory / f"results-{suffix}.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2)
    )


if __name__ == "__main__":
    asyncio.run(main())

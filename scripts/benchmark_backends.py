"""Opt-in, real-model ASR comparison and paced subtitle-pipeline replay.

Requires a local fixture manifest, installed MLX snapshots and whisper-server.
No synthetic inference, downloading, browser capture or production defaults changed.
"""

import argparse
import asyncio
import io
import json
import math
import platform
import time
import unicodedata
import wave
import zlib
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import numpy as np
import webrtcvad

from live_subs.audio import AudioJob, Segmenter
from live_subs.engine import MLXEngine, Recognition, rejection_reason
from live_subs.pipeline import Pipeline


def normalized(text, language):
    text = unicodedata.normalize("NFKC", text).lower()
    text = "".join(c for c in text if not unicodedata.category(c).startswith(("P", "S")))
    return text.split() if language == "en" else list("".join(text.split()))


def edit_distance(reference, hypothesis):
    previous = list(range(len(hypothesis) + 1))
    for i, expected in enumerate(reference, 1):
        current = [i]
        for j, actual in enumerate(hypothesis, 1):
            current.append(
                min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (expected != actual))
            )
        previous = current
    return previous[-1]


def quality(text, fixture):
    reference = normalized(fixture["reference"], fixture["language"])
    hypothesis = normalized(text, fixture["language"])
    if not reference:
        raise ValueError("Fixture reference cannot be empty")
    return {"edits": edit_distance(reference, hypothesis), "reference_units": len(reference)}


def pcm_for(fixture, directory):
    with wave.open(str(directory / fixture["file"])) as f:
        if (f.getnchannels(), f.getsampwidth(), f.getframerate()) != (1, 2, 16000):
            raise ValueError("Fixtures must be 16 kHz mono PCM16 WAV")
        return f.readframes(f.getnframes()) + bytes(32000)


def speech_frames(pcm):
    vad = webrtcvad.Vad(2)
    for offset in range(0, len(pcm), 640):
        frame = pcm[offset : offset + 640].ljust(640, b"\0")
        samples = np.frombuffer(frame, dtype="<i2").astype(np.float32)
        rms = float(np.sqrt(np.mean(samples * samples)))
        yield frame, rms >= 100 and vad.is_speech(frame, 16000)


class NativeASR:
    """Experimental HTTP adapter; confidence statistics are not identical to MLX."""

    def __init__(self, url):
        parsed = urlsplit(url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
            raise ValueError("Native benchmark endpoint must be an HTTP loopback service")
        self.client = httpx.Client(base_url=url, timeout=60, trust_env=False)
        self.client.get("/health").raise_for_status()

    def transcribe(self, pcm, language):
        wav = io.BytesIO()
        with wave.open(wav, "wb") as f:
            f.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
            f.writeframes(pcm)
        fields = {
            "language": language,
            "response_format": "verbose_json",
            "temperature": "0",
            "temperature_inc": "0",
            "best_of": "1",
            "beam_size": "1",
            "no_timestamps": "true",
            "no_language_probabilities": "true",
        }
        files = {k: (None, v) for k, v in fields.items()}
        files["file"] = ("segment.wav", wav.getvalue(), "audio/wav")
        response = self.client.post("/inference", files=files)
        response.raise_for_status()
        result = response.json()
        # Native verbose JSON omits compression ratio. Compute the same text statistic.
        for segment in result["segments"]:
            encoded = segment["text"].encode()
            segment["compression_ratio"] = len(encoded) / len(zlib.compress(encoded))
        reason = rejection_reason(result)
        detected = {"english": "en", "japanese": "ja"}.get(result["language"], result["language"])
        return Recognition("" if reason else result["text"].strip(), detected, reason)


class CombinedEngine:
    def __init__(self, asr, translator):
        self.asr = asr
        self.translator = translator

    def transcribe(self, pcm, language):
        return self.asr.transcribe(pcm, language)

    def translate(self, *args):
        return self.translator.translate(*args)


def percentile(values, q):
    return sorted(values)[max(0, math.ceil(len(values) * q) - 1)] if values else None


def summarize(rows, mode):
    groups = {}
    for backend in sorted({r["backend"] for r in rows}):
        for language in ("en", "ja"):
            selected = [r for r in rows if r["backend"] == backend and r["language"] == language]
            if not selected:
                continue
            counts = Counter()
            for row in selected:
                counts.update(row["counts"])
            result = {
                "utterance_runs": len(selected),
                "counts": dict(counts),
                "error_rate": sum(r["edits"] for r in selected)
                / sum(r["reference_units"] for r in selected),
                "error_metric": "WER" if language == "en" else "CER",
            }
            metrics = [v for row in selected for v in row["metrics"]]
            keys = (
                ("asr_ms",)
                if mode == "asr"
                else ("asr_ms", "translation_ms", "first_zh_ms", "tail_ms")
            )
            for key in keys:
                values = [m[key] for m in metrics if key in m]
                result[key] = {
                    "n": len(values),
                    "p50": percentile(values, 0.5),
                    "p95": percentile(values, 0.95),
                }
            groups[f"{backend}/{language}"] = result
    return groups


async def run_asr(engine, executor, fixture, pcm, args):
    segmenter = Segmenter(max_frames=round(args.max_seconds * 50), partial_frames=10000)
    jobs = []
    for index, (frame, speech) in enumerate(speech_frames(pcm)):
        jobs.extend(segmenter.feed(frame, speech, (index + 1) * 0.02))
    jobs.extend(segmenter.flush())
    if args.whole_utterance:
        duration = len(pcm) / 32000
        jobs = [AudioJob(1, pcm, 0, duration, True, duration - 1, 0)]
    metrics, text, counts = [], [], Counter()
    for job in jobs:
        began = time.perf_counter()
        counts["segments"] += 1
        try:
            result = await asyncio.get_running_loop().run_in_executor(
                executor, engine.transcribe, job.pcm, fixture["language"]
            )
            elapsed = (time.perf_counter() - began) * 1000
            counts[result.reason or "recognized"] += 1
            metrics.append(
                {
                    "asr_ms": round(elapsed, 2),
                    "reason": result.reason,
                    "text": result.text,
                    "audio_ms": round(len(job.pcm) / 32),
                }
            )
            text.append(result.text)
        except Exception as exc:
            counts["errors"] += 1
            metrics.append({"error": str(exc)})
    source = (" " if fixture["language"] == "en" else "").join(text)
    return {
        "source": source,
        "counts": dict(counts),
        "metrics": metrics,
        **quality(source, fixture),
    }


async def run_realtime(engine, executor, fixture, pcm, args):
    events = []

    async def send(event):
        event = dict(event)
        event["received_ms"] = time.time() * 1000
        events.append(event)

    epoch = time.time() * 1000
    pipeline = Pipeline(engine, executor, send, fixture["language"], "zh-en", epoch)
    segmenter = Segmenter(
        max_frames=round(args.max_seconds * 50), partial_frames=40 if args.partials else 10000
    )
    worker = asyncio.create_task(pipeline.run())
    started = time.perf_counter()
    for index, (frame, speech) in enumerate(speech_frames(pcm)):
        await asyncio.sleep(max(0, started + (index + 1) * 0.02 - time.perf_counter()))
        for job in segmenter.feed(frame, speech, (index + 1) * 0.02):
            await pipeline.submit(job)
    for job in segmenter.flush():
        await pipeline.submit(job)
    pipeline.finish()
    await asyncio.wait_for(worker, 90)
    transcripts = [e["source"] for e in events if e["type"] == "transcript" and e["final"]]
    source = (" " if fixture["language"] == "en" else "").join(transcripts)
    metrics = [e for e in events if e["type"] == "translation"]
    return {
        "source": source,
        "counts": dict(pipeline.counts),
        "metrics": metrics,
        "events": events,
        **quality(source, fixture),
    }


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--models", type=Path, default=Path(".local/models.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=["asr", "realtime"], default="asr")
    parser.add_argument("--backend", choices=["mlx", "cpp", "both"], default="both")
    parser.add_argument("--native-url", default="http://127.0.0.1:18766")
    parser.add_argument("--native-label", default="cpp-metal")
    parser.add_argument("--native-provenance", type=Path)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--max-seconds", type=float, default=3)
    parser.add_argument("--partials", action="store_true")
    parser.add_argument("--whole-utterance", action="store_true", help="ASR-only quality control")
    args = parser.parse_args()
    if args.repeats < 1 or not 0.5 <= args.max_seconds <= 3:
        parser.error("repeats >= 1 and .5 <= max-seconds <= 3 required")
    if args.whole_utterance and args.mode != "asr":
        parser.error("whole-utterance is an offline ASR quality control, not a streaming mode")
    fixtures = json.loads(args.fixtures.read_text())["fixtures"]
    if not fixtures:
        parser.error("empty fixture manifest")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    with ThreadPoolExecutor(max_workers=1) as executor:
        loop = asyncio.get_running_loop()
        began = time.perf_counter()
        mlx = await loop.run_in_executor(executor, MLXEngine, args.models)
        init_ms = round((time.perf_counter() - began) * 1000)
        engines = {"mlx": mlx}
        native = None
        if args.backend != "mlx":
            native = NativeASR(args.native_url)
            engines["cpp"] = CombinedEngine(native, mlx)
        if args.backend == "cpp":
            del engines["mlx"]
        # Explicit warm-up outside recorded samples, using real audio for each language.
        for language in ("en", "ja"):
            first = next(f for f in fixtures if f["language"] == language)
            pcm = pcm_for(first, args.fixtures.parent)[:96000]
            for engine in engines.values():
                await loop.run_in_executor(executor, engine.transcribe, pcm, language)
        report = {
            "mode": args.mode,
            "platform": platform.platform(),
            "machine": platform.machine(),
            "models": {
                kind: {k: v for k, v in data.items() if k != "path"}
                for kind, data in json.loads(args.models.read_text()).items()
            },
            "mlx_init_ms": init_ms,
            "repeats": args.repeats,
            "max_seconds": args.max_seconds,
            "partials": args.partials,
            "whole_utterance": args.whole_utterance,
            "input_language": "fixed per fixture",
            "transport": "in-process paced pipeline; native ASR includes loopback HTTP",
            "quantization": "MLX 4-bit vs whisper.cpp Q5_0; not bit-identical",
            "confidence": "Native confidence normalization differs; record rejections",
            "native_label": args.native_label,
            "native_provenance": (
                json.loads(args.native_provenance.read_text()) if args.native_provenance else None
            ),
            "fixtures": json.loads(args.fixtures.read_text()),
            "rows": rows,
        }
        try:
            for repeat in range(args.repeats):
                for fixture in fixtures:
                    pcm = pcm_for(fixture, args.fixtures.parent)
                    order = list(engines) if repeat % 2 == 0 else list(reversed(engines))
                    for name in order:
                        mlx.translation_caches.clear()
                        run = run_asr if args.mode == "asr" else run_realtime
                        result = await run(engines[name], executor, fixture, pcm, args)
                        row = {
                            "repeat": repeat,
                            "fixture": fixture["id"],
                            "backend": name,
                            "language": fixture["language"],
                            **result,
                        }
                        rows.append(row)
                        report["summary"] = summarize(rows, args.mode)
                        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
                        print(
                            json.dumps(
                                {
                                    k: row[k]
                                    for k in [
                                        "repeat",
                                        "fixture",
                                        "backend",
                                        "counts",
                                        "edits",
                                        "reference_units",
                                    ]
                                }
                            ),
                            flush=True,
                        )
        finally:
            if native:
                native.client.close()
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2), flush=True)
    if any(r["counts"].get("errors") for r in rows):
        raise SystemExit("Inference errors occurred; inspect the saved report")


if __name__ == "__main__":
    asyncio.run(main())

"""Real-model Swift/Rust pilots using the first-stage fixtures and production scoring.

Build workers and prepare models first. Raw output stays in ignored .local.
Translation comparison uses identical prompt IDs and fresh KV caches per request.
This measures components, not a native browser-to-overlay production service.
"""

import argparse
import asyncio
import json
import queue
import re
import subprocess
import threading
import time
import wave
import zlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
from benchmark_backends import pcm_for, percentile, run_asr, summarize

from live_subs.engine import MLXEngine, Recognition, parse_translation, rejection_reason


class Worker:
    """Resident local process with bounded waits and separate diagnostic output."""

    def __init__(self, command, log, timeout=600):
        self.log = Path(log).open("w")
        self.process = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log, text=True
        )
        self.lines = queue.Queue()
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()
        try:
            if not self.receive(timeout).get("ready"):
                raise RuntimeError("Native worker did not report readiness")
        except Exception:
            self.close()
            raise

    def _read(self):
        for line in self.process.stdout:
            self.lines.put(line)
        self.lines.put(None)

    def receive(self, timeout):
        deadline = time.monotonic() + timeout
        while True:
            line = self.lines.get(timeout=max(0, deadline - time.monotonic()))
            if line is None:
                raise RuntimeError("Native worker exited; inspect its local log")
            try:
                result = json.loads(line)
            except json.JSONDecodeError:
                self.log.write(line)
                self.log.flush()
                continue
            if "error" in result:
                raise RuntimeError(result["error"])
            return result

    def request(self, value):
        self.process.stdin.write(json.dumps(value, ensure_ascii=False) + "\n")
        self.process.stdin.flush()
        return self.receive(90)

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        self.log.close()


class WorkerASR:
    def __init__(self, worker, directory, default_gates=False):
        self.worker = worker
        self.path = (directory / "segment.wav").resolve()
        self.default_gates = default_gates

    def transcribe(self, pcm, language):
        with wave.open(str(self.path), "wb") as wav:
            wav.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
            wav.writeframes(pcm)
        result = self.worker.request(
            {
                "operation": "asr",
                "path": str(self.path),
                "language": language,
                "default_gates": self.default_gates,
            }
        )
        for segment in result.get("segments", []):
            encoded = segment.get("text", "").encode()
            segment["compression_ratio"] = len(encoded) / len(zlib.compress(encoded))
        reason = rejection_reason(result)
        return Recognition("" if reason else result["text"].strip(), language, reason)


class CaptureTokenizer:
    """Record the actual production prompt, without maintaining a second template."""

    def __init__(self, tokenizer):
        self.original_encode = tokenizer.encode
        self.tokens = None

    def encode(self, *args, **kwargs):
        self.prompt = args[0]
        self.tokens = self.original_encode(*args, **kwargs)
        return self.tokens


def tts_content_issues(fixture_id, translation):
    """Reuse the original smoke-test content requirements; not a general quality score."""
    if fixture_id not in {"en-tts", "ja-tts"}:
        return None
    zh, en = translation["zh"], translation["en"].lower()
    checks = {
        "missing_chinese_time": "三点" in zh or "3点" in zh,
        "missing_chinese_meeting": "会议" in zh,
        "missing_chinese_computer": "电脑" in zh or "计算机" in zh,
        "missing_english_time": "three" in en or "3" in en,
        "missing_english_meeting_or_computer": "meeting" in en
        and ("computer" in en or "laptop" in en),
        "invented_day_period": "上午" not in zh
        and "下午" not in zh
        and not re.search(r"\b(?:am|pm|morning|afternoon)\b", en.replace(".", "")),
    }
    return [name for name, passed in checks.items() if not passed]


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["asr", "translation"], required=True)
    parser.add_argument("--route", choices=["swift", "rust"], required=True)
    parser.add_argument(
        "--fixtures", type=Path, default=Path(".local/backend-fixtures/manifest.json")
    )
    parser.add_argument("--models", type=Path, default=Path(".local/models.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--whole-utterance", action="store_true")
    parser.add_argument("--whisperkit-default-gates", action="store_true")
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("repeats must be positive")
    if args.whole_utterance and args.mode != "asr":
        parser.error("whole-utterance is only an ASR quality control")
    if args.whisperkit_default_gates and (args.route != "swift" or args.mode != "asr"):
        parser.error("whisperkit-default-gates only applies to Swift ASR")
    args.max_seconds = 3
    args.output.parent.mkdir(parents=True, exist_ok=True)
    directory = Path(".local/native-route-runtime")
    await asyncio.to_thread(directory.mkdir, parents=True, exist_ok=True)
    fixtures = json.loads(args.fixtures.read_text())["fixtures"]
    config = json.loads(args.models.read_text())
    if args.route == "rust":
        command = ["experiments/native-rust/target/release/tingsub-native-pilot"]
    elif args.mode == "asr":
        command = [
            "experiments/native-swift/.build/release/ASRPilot",
            ".local/native/whisperkit-models/openai_whisper-large-v3-v20240930_626MB",
            ".local/native/whisperkit-tokenizer",
        ]
    else:
        command = [
            "experiments/native-swift/.build/release/TranslationPilot",
            config["translation"]["path"],
        ]
    worker = Worker(command, directory / f"{args.route}-{args.mode}.log")
    rows = []
    report = {
        "mode": args.mode,
        "route": args.route,
        "repeats": args.repeats,
        "whole_utterance": args.whole_utterance,
        "max_seconds": args.max_seconds,
        "prompt_cache": "fresh per translation request, all backends",
        "input_language": "fixed",
        "browser_end_to_end": False,
        "whisperkit_default_gates": args.whisperkit_default_gates,
        "rows": rows,
    }
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            loop = asyncio.get_running_loop()
            mlx = await loop.run_in_executor(executor, MLXEngine, args.models)
            native = WorkerASR(worker, directory, args.whisperkit_default_gates)
            if args.mode == "asr":
                for language in ("en", "ja"):
                    fixture = next(f for f in fixtures if f["language"] == language)
                    pcm = pcm_for(fixture, args.fixtures.parent)[:96000]
                    for engine in (mlx, native):
                        await loop.run_in_executor(executor, engine.transcribe, pcm, language)
            else:
                capture = CaptureTokenizer(mlx.tokenizer)
                object.__setattr__(mlx.tokenizer, "encode", capture.encode)
                # Use production prompt construction and tokenizer for EVERY backend.
                prompts = {}
                for fixture in fixtures:
                    mlx.translation_caches.clear()
                    await loop.run_in_executor(
                        executor, mlx.translate, fixture["reference"], fixture["language"], "zh-en"
                    )
                    prompts[fixture["id"]] = list(capture.tokens)
                    if args.route == "rust":
                        # GGUF token IDs must mean the same thing before reusing them.
                        check = await asyncio.to_thread(
                            httpx.post,
                            "http://127.0.0.1:18767/tokenize",
                            json={
                                "content": capture.prompt,
                                "add_special": False,
                                "parse_special": True,
                            },
                            trust_env=False,
                            timeout=30,
                        )
                        check.raise_for_status()
                        if check.json()["tokens"] != prompts[fixture["id"]]:
                            raise RuntimeError("GGUF prompt token IDs differ from MLX")
                for language in ("en", "ja"):
                    fixture = next(f for f in fixtures if f["language"] == language)
                    worker.request({"operation": "translate", "tokens": prompts[fixture["id"]]})
            for repeat in range(args.repeats):
                order = ["mlx", args.route] if repeat % 2 == 0 else [args.route, "mlx"]
                for fixture in fixtures:
                    for backend in order:
                        if args.mode == "asr":
                            result = await run_asr(
                                mlx if backend == "mlx" else native,
                                executor,
                                fixture,
                                pcm_for(fixture, args.fixtures.parent),
                                args,
                            )
                        else:
                            mlx.translation_caches.clear()
                            started = time.perf_counter()
                            result = {}
                            try:
                                if backend == "mlx":
                                    translation = await loop.run_in_executor(
                                        executor,
                                        mlx.translate,
                                        fixture["reference"],
                                        fixture["language"],
                                        "zh-en",
                                    )
                                else:
                                    response = worker.request(
                                        {"operation": "translate", "tokens": prompts[fixture["id"]]}
                                    )
                                    raw = '{"zh":' + response.get(
                                        "text", response.get("content", "")
                                    )
                                    result["raw"] = raw
                                    translation = parse_translation(
                                        raw, fixture["reference"], fixture["language"], "zh-en"
                                    )
                                result.update(
                                    translation=translation,
                                    success=True,
                                    content_issues=tts_content_issues(fixture["id"], translation),
                                )
                            except Exception as exc:
                                result.update(error=str(exc), success=False)
                            result["translation_ms"] = round(
                                (time.perf_counter() - started) * 1000, 2
                            )
                        row = {
                            "repeat": repeat,
                            "fixture": fixture["id"],
                            "language": fixture["language"],
                            "backend": backend,
                            **result,
                        }
                        rows.append(row)
                        if args.mode == "asr":
                            report["summary"] = summarize(rows, "asr")
                        else:
                            report["summary"] = translation_summary(rows)
                        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
                        print(
                            json.dumps(
                                {
                                    k: row[k]
                                    for k in row
                                    if k
                                    in {
                                        "repeat",
                                        "fixture",
                                        "backend",
                                        "counts",
                                        "edits",
                                        "success",
                                        "translation_ms",
                                    }
                                }
                            ),
                            flush=True,
                        )
    finally:
        worker.close()
    print(json.dumps(report["summary"], indent=2))
    failed = any(
        r.get("counts", {}).get("errors") or r.get("success") is False or r.get("content_issues")
        for r in rows
    )
    report["inference_and_content_checks_passed"] = not failed
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    if failed:
        raise SystemExit("Inference or content checks failed; inspect raw report")


def translation_summary(rows):
    result = {}
    for backend in sorted({r["backend"] for r in rows}):
        for language in ("en", "ja"):
            selected = [r for r in rows if r["backend"] == backend and r["language"] == language]
            if not selected:
                continue
            values = [r["translation_ms"] for r in selected if r["success"]]
            result[f"{backend}/{language}"] = {
                "attempts": len(selected),
                "successes": len(values),
                "p50_ms": percentile(values, 0.5),
                "p95_ms": percentile(values, 0.95),
            }
            checked = [r for r in selected if r.get("content_issues") is not None]
            result[f"{backend}/{language}"].update(
                content_checked=len(checked),
                content_passed=sum(not r["content_issues"] for r in checked),
            )
    return result


if __name__ == "__main__":
    asyncio.run(main())

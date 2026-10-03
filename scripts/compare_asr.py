"""Compare auto-language ASR paths using identical local models and audio.

Stop the subtitle service first. Requires benchmark.py's generated WAV fixtures.
Both methods perform real inference; results include full transcripts for review.
"""

import json
import statistics
import time
import wave
from pathlib import Path

import numpy as np

from live_subs.engine import MLXEngine, reliable_transcript


def main():
    engine = MLXEngine(Path(".local/models.json"))
    results = []
    for language in ("en", "ja"):
        with wave.open(f".local/benchmark/{language}.wav") as audio_file:
            assert (audio_file.getnchannels(), audio_file.getsampwidth(),
                    audio_file.getframerate()) == (1, 2, 16000)
            pcm = audio_file.readframes(audio_file.getnframes())
        audio = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768
        for attempt in range(3):
            # Alternate order to reduce warm-cache / temperature bias.
            order = ("old", "new") if attempt % 2 == 0 else ("new", "old")
            for method in order:
                started = time.perf_counter()
                if method == "old":
                    result = engine.whisper.transcribe(
                        audio, path_or_hf_repo=engine.asr_path, language=None,
                        temperature=0.0, condition_on_previous_text=False,
                        word_timestamps=False, sample_len=128, verbose=None,
                    )
                    text, detected = reliable_transcript(result), result["language"]
                else:
                    text, detected = engine.transcribe(pcm, "auto")
                elapsed = round((time.perf_counter() - started) * 1000)
                assert detected == language, (method, detected, text)
                expected = ("meeting", "laptop") if language == "en" else ("会議", "パソコン")
                assert all(word in text.lower() for word in expected), (method, text)
                row = dict(language=language, method=method, ms=elapsed, text=text)
                results.append(row)
                print(json.dumps(row, ensure_ascii=False), flush=True)
    Path(".local/benchmark/asr-before-after.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2)
    )
    for language in ("en", "ja"):
        for method in ("old", "new"):
            median = statistics.median(
                row["ms"] for row in results
                if row["language"] == language and row["method"] == method
            )
            print(f"{language} {method}: median {median}ms")


if __name__ == "__main__":
    main()

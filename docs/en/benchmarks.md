[English](../en/benchmarks.md) · [简体中文](../zh-CN/benchmarks.md) · [Index](README.md)

# Performance and validation

## What the numbers mean

| Metric | Definition |
| --- | --- |
| First text / 本段首字 | First VAD speech in this segment to its first recognized text |
| First Chinese / 首中 | First VAD speech in this segment to its first complete Chinese text |
| Tail / 句尾 | Last VAD speech in this segment to complete bilingual output |
| ASR / 识别 | Recognition call duration |
| Translation / 翻译 | Translation call duration, including early-output delivery |
| Queue | Monotonic time between queuing a job and beginning inference |

The overlay measures arrival/render-side timing; server metrics are measured before sending, so they can differ slightly. Forced splits start a new segment clock, not a new natural sentence. Draft settings affect first-text and GPU contention. VAD speech boundaries are estimates, not hand-labeled acoustic ground truth.

Session counters include finalized segments, translated segments, low confidence, repetition, silence/empty, dropped work and errors. P50/P95 are a rolling window of at most **256 successful translations**. Rejected, dropped and failed segments are excluded from that distribution, so always publish their counts too. Error counters can include draft failures and are not by themselves a mutually exclusive final-segment success rate.

## Reproducible smoke tests

On an Apple Silicon Mac, prepare models, install the Samantha (English) and Kyoko (Japanese) macOS voices, and start the service. Stop other caption sessions first.

```sh
uv run --frozen python scripts/benchmark.py
uv run --frozen python scripts/benchmark.py --auto-language --no-partials
npm ci
npx playwright install chromium
npm run test:live
```

`benchmark.py` generates speech with macOS `say`, streams it at 20 ms cadence to the real service and asserts preserved content (meeting, three o'clock, bringing a computer, no invented AM/PM). It writes `.local/benchmark/results-partials.json` or `results-no-partials-auto.json` and the audio fixtures.

`test:live` requires those generated fixtures and a running service using the same `.local/token`. It plays them in isolated Chromium and exercises actual tabCapture → AudioWorklet → WebSocket → MLX → overlay. It uses browser debugging flags only in its disposable test profile. Results are in `.local/benchmark/browser-capture.json`.

For direct model checks, **stop the service first**:

```sh
uv run --frozen python scripts/check_translation.py
uv run --frozen python scripts/check_streaming.py
uv run --frozen python scripts/compare_asr.py
```

These check short translation cases, early Chinese delivery/cache isolation and the old/new ASR path respectively. Missing models or failed assertions fail the run; there is no fallback to fake inference. Model outputs can vary with upstream revisions and runtime versions.

## Evidence boundaries

The initial implementation was exercised locally on an Apple M4 Pro with 48 GB RAM using real English/Japanese synthesized speech, including browser audio capture. The historical tested model revisions are listed in [models](models.md). Raw local recordings, transcripts and machine-specific logs are intentionally not published. Re-run the scripts on your own checkout; these notes are not a reproducible public benchmark dataset or a CI performance guarantee.

The [2026-10-03 backend pilot](backend-pilot.md) adds local MLX/whisper.cpp measurements and WER/CER for six public human-read clips plus two TTS fixtures. It includes sanitized numeric evidence and reproduction commands, but does not constitute a representative livestream evaluation set. There is still no redistributed, license-reviewed natural-speech corpus, human translation scoring or long-session reliability benchmark. Synthetic smoke tests establish that specific content survives the pipeline; they do not establish robustness to real livestreams. Typical failure cases include music, multiple speakers, proper nouns, short clips and words cut by the 3-second segment boundary.

When sharing results, include commit, chip/RAM, macOS/Chrome, model revisions, draft/language/display settings, warm-up, sample count, all rejection/drop/error counts, and latency P50/P95. Use audio you are allowed to share and redact tokens/private paths. Compare the same audio and settings; lower latency caused by missing more speech is not an improvement.

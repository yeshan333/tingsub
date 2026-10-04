[English](../en/benchmarks.md) · [简体中文](../zh-CN/benchmarks.md) · [Index](README.md)

# Performance and validation

## Test reports

Reports distinguish model-only experiments from browser end-to-end validation and retain failures and untested conditions. Check [models](models.md) separately for integration status.

| Date | Report | Scope | Current guidance |
| --- | --- | --- | --- |
| 2026-10-05 | [Whisper vs Qwen3-ASR](asr-comparison-2026-10-05.md) | M4 Pro; 6 human read-speech clips, 6 synthetic controls, 2 synthetic-accompaniment variants and silence | Keep Whisper default; 0.6B is a candidate for a future optional fast mode |

The report includes [sanitized per-call timings and aggregates](../benchmarks/asr-2026-10-05.json). Add dated reports for future tests and retain historical measurements rather than replacing them with faster rechecks.

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

`check_translation.py` runs 14 authored text scenarios twice: with an empty translation cache and then in reverse order with cache reuse (28 scored calls). Before reuse, two separate, unscored translations populate both prompt-cache variants. Each row records `cached_tokens_before`; a reuse row without a populated cache fails. It checks both sentences, target languages, ambiguous versus explicit AM/PM, negation, numbers bound to their clock/ticket context, allowed Latin technical names, English source preservation, and original-plus-Chinese mode. It saves outputs, failures, timings and the installed translation model revision in ignored `.local/benchmark/translation-check.json`; any failure exits nonzero. Its content patterns apply only to these examples, not arbitrary speech, and are not a general quality score or runtime output filter.

`check_streaming.py` checks early Chinese delivery and cache isolation, including the full two-sentence regression. It also primes both cache variants before the reuse pass and records the pre-call cached token count. `compare_asr.py` compares the old/new ASR path. Missing models or failed assertions fail the run; there is no fallback to fake inference. Model outputs can vary with upstream revisions and runtime versions.

## Translation prompt regression

On Apple M4 Pro / 48 GB, macOS 27.0.1, Python 3.12.11, MLX 0.32.3 and MLX LM 0.32.0, using the Qwen 3B revision in [models](models.md), the same 28 checks passed **24/28 before** and **28/28 after** this prompt change. The baseline is `eda8e783f916c52239cfe6966439478045421b6f`. These results were rerun after correcting cache priming and checks for swapped numbers, ordinary “am” versus a time abbreviation, and “not useful” versus “not use.” The previous prompt put an English sentence into `zh` for both the two-sentence meeting request and the technical negation example, with and without cache reuse. Explicit target-language instructions plus a distinct two-sentence bilingual example fixed those observed failures. Models, decoding settings and segmentation are unchanged; there is still one generation call per translation.

The latest checks also bind day-period words to the clock expression and Chinese negation to the app/API usage relationship. They were checked against saved baseline outputs and a fresh current-model run.

These are authored text regressions, not unseen evaluation data or a livestream test. Prompt exploration still found semantic errors outside the guarded cases: `切符を忘れないでください。` in the train example became “do not forget to buy your ticket,” adding a purchase; `田中さん` retained Japanese kana in Chinese and became “Mr. Tanaka” in English, inferring gender. Those problems remain unresolved. Passing this check does not certify arbitrary captions; no correction, retry, or caption dropping hides them.

## Evidence boundaries

The initial implementation was exercised locally on an Apple M4 Pro with 48 GB RAM using real English/Japanese synthesized speech, including browser audio capture. The historical tested model revisions are listed in [models](models.md). Raw local recordings, full transcripts and machine-specific logs are intentionally not published; the new report shares sanitized measurements and public dataset sample identifiers. Re-run the scripts on your own checkout; these notes are not a reproducible public benchmark dataset or a CI performance guarantee.

The [2026-10-05 ASR comparison](asr-comparison-2026-10-05.md) adds a small FLEURS human read-speech sample with WER/CER. There is still no large natural-livestream evaluation, systematic human translation scoring or long-session reliability benchmark. Synthetic smoke tests establish that specific content survives the pipeline; neither those checks nor the small read-speech sample establish robustness to real livestreams. Typical failure cases include music, multiple speakers, proper nouns, short clips and words cut by the 3-second segment boundary.

When sharing results, include commit, chip/RAM, macOS/Chrome, model revisions, draft/language/display settings, warm-up, sample count, all rejection/drop/error counts, and latency P50/P95. Use audio you are allowed to share and redact tokens/private paths. Compare the same audio and settings; lower latency caused by missing more speech is not an improvement.

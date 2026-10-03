[English](../en/backend-pilot.md) · [简体中文](../zh-CN/backend-pilot.md) · [Index](README.md)

# Local backend pilot — 2026-10-03

Keep the current MLX backend for now. On this machine and small corpus, whisper.cpp with Metal was about 20% slower in median ASR time. Its Core ML build improved isolated ASR medians by only 1.6–1.9%, without a consistent benefit through translation. These measurements do not justify a Python-to-native rewrite. The more actionable finding is recognition damage at forced segment boundaries.

The opt-in scripts do not change the service, extension or defaults. [Numeric results](../benchmarks/backend-pilot-2026-10-03.json) include per-run counts, per-clip edit totals, timings, model revisions and audio hashes. Audio, reference transcripts, model output and private paths remain local.

The follow-up [Swift and Rust component pilots](native-routes.md) test the other two implementation routes and document translation content failures.

## Setup and limits

- Apple M4 Pro, 48 GB RAM, macOS 27.0.1, Python 3.12.11; production code at `eda8e783f916c52239cfe6966439478045421b6f`.
- MLX 0.32.3, mlx-whisper 0.4.3, mlx-lm 0.32.0. Native: whisper.cpp 1.8.4 (`9386f239401074690479731c1e41683fbbeac557`), system GGML 0.11.0, four CPU threads, greedy decoding. The lockfile pins Python dependencies.
- Same Whisper large-v3-turbo family, but **MLX 4-bit and GGML Q5_0 are different weights/quantization formats**. Core ML also uses a separate compiled encoder artifact. Decoder and confidence-score details differ. This compares deployable configurations, not interpreter overhead in isolation.
- Both paths use the existing MLX Qwen2.5-3B-Instruct-4bit translator, fixed input language, Chinese/English output, drafts off, existing VAD and 3-second maximum segments. Translation history is cleared between utterances.
- Eight distinct recordings, 43.857 seconds total: the first three viewer rows of English [LibriSpeech dummy](https://huggingface.co/datasets/hf-internal-testing/librispeech_asr_dummy), the first three of Japanese [JSUT](https://huggingface.co/datasets/japanese-asr/ja_asr.jsut_basic5000), and two macOS TTS smoke fixtures. The human recordings are **read speech**, not noisy livestreams. They were selected before inspecting recognition results. Dataset revisions and hashes are in the numeric artifact. Raw audio is not redistributed here; consult each source's terms before reuse.
- ASR runs warm both languages before measurement and alternate backend order across repeats. Three repeats for segmented ASR; two for whole-utterance controls and paced replay. Repeats reuse the same clips and are not additional independent speech samples. Model load and ASR warm-up are excluded. Translation has no separate warm-up pass.
- ASR-only runs time real calls on precomputed segments. Paced replay feeds 20 ms PCM frames through the real `Segmenter` and `Pipeline`, including VAD wait, scheduling, recognition and translation. Native timings also include loopback HTTP/WAV transfer. **Browser capture, WebSocket delivery and overlay rendering are not measured.**
- Core ML was built with fallback disabled, and startup confirmed that its encoder loaded. This does not establish which Apple compute unit handled every operation; ANE utilization was not profiled. No power, peak-memory, long-session, automatic-language or human translation-quality evaluation was performed. This was a normal desktop session, not an isolated performance lab.

## Isolated recognition

Values are P50 / P95 milliseconds. Each backend has 33 English and 24 Japanese segment calls per comparison. All returned ASR calls, including rejected results, enter this latency table.

| Comparison | Backend | English | Japanese | Recognized / total |
| --- | --- | --- | --- | --- |
| Metal | MLX | 487.70 / 497.55 | 494.77 / 503.70 | 57 / 57 |
| Metal | whisper.cpp Metal | 584.90 / 591.91 | 590.81 / 604.13 | 57 / 57 |
| Core ML | MLX, fresh baseline | 488.32 / 495.12 | 491.43 / 499.29 | 57 / 57 |
| Core ML | whisper.cpp Core ML | 479.30 / 488.17 | 483.54 / 496.91 | 54 / 57 |

Core ML rejected one Japanese tail as low confidence in all three repeats. There were no inference errors. Faster inference alone is insufficient when coverage or recognition quality changes.

## Paced recognition and translation

This is the interleaved MLX/Core ML run with two repeats. “First Chinese” starts at the first VAD speech frame **of each segment**; “tail” starts at its last speech frame. Neither is a whole-recording startup metric. Values are P50 / P95 milliseconds and cover **successful translations only**. Other counters were zero; no drops or inference errors occurred.

| Backend / language | Translated / segments | Low confidence | First Chinese | Tail | ASR | Translation |
| --- | --- | --- | --- | --- | --- | --- |
| MLX / English | 22 / 22 | 0 | 3112 / 3753 | 867 / 1067 | 528 / 539 | 179 / 330 |
| Core ML / English | 22 / 22 | 0 | 3092 / 3759 | 846 / 1047 | 488 / 559 | 188 / 336 |
| MLX / Japanese | 16 / 16 | 0 | 2812 / 3707 | 1028 / 1372 | 524 / 545 | 265 / 507 |
| Core ML / Japanese | 14 / 16 | 2 | 3503 / 3751 | 993 / 1435 | 518 / 577 | 415 / 522 |

English median first-Chinese latency differs by just 20 ms. The Japanese distributions contain different accepted segments, and different recognized text also changes translation work. They cannot establish a clean backend speed ranking. A separate MLX-only replay is retained in the artifact as a preliminary baseline, not substituted for this interleaved comparison.

## Segment boundaries matter

Quality uses aggregate word edit distance for English (WER) and character edit distance for Japanese (CER). Normalization applies NFKC, lowercasing, punctuation/symbol removal and whitespace handling. It does not equate Japanese kanji/kana spellings or digits with number words. Missing output remains in the denominator; entire missing utterances count as deletions. These are recognition scores, not translation scores.

| Input policy | Backend | English WER, four clips | Japanese CER, four clips |
| --- | --- | --- | --- |
| 3-second segments | MLX | 5.71% | 31.52% |
| 3-second segments | whisper.cpp Metal | 7.14% | 31.52% |
| 3-second segments | whisper.cpp Core ML | 7.14% | 30.43% |
| Whole utterance, offline control | MLX | 4.29% | 4.35% |
| Whole utterance, offline control | whisper.cpp Metal | 4.29% | 3.26% |

On the **three human-read Japanese clips alone**, both segmented MLX and Metal produced 28 edits / 65 reference characters (43.08%). Whole-utterance inference reduced this to 3 / 65 (4.62%) for MLX and 2 / 65 (3.08%) for Metal. Short tails sometimes produced unrelated closing thanks. Confidence filtering did not catch every hallucination.

This is a useful failure reproduction, not a representative Japanese accuracy benchmark. Waiting for an entire utterance is not the proposed live solution: one English clip lasts 12.485 seconds. The next experiment should preserve recognition context across boundaries and commit stable text without duplicating or deleting words, then compare quality and latency on a larger corpus and real browser sessions. Simply shortening segments is not justified by these results.

## Reproduce locally

Use an Apple Silicon Mac with models prepared as described in [installation](installation.md). Stop other subtitle/model sessions. Install `ffmpeg`, the Samantha/Kyoko macOS voices, and whisper.cpp 1.8.4. Downloads happen only during preparation; inference stays local. Budget disk space for the native model, encoder and build.

```sh
uv sync --frozen
uv run --frozen python scripts/prepare_backend_fixtures.py
```

The fixture script reads the current dataset viewer rows. Compare the resulting manifest revisions/hashes against the published artifact before treating a rerun as the same input. TTS and conversion output may vary with OS/ffmpeg versions. Preserve `.local/backend-fixtures` for repeated comparisons.

Download the pinned native artifacts:

```sh
uv run --frozen python - <<'PY'
from huggingface_hub import hf_hub_download
for name in ("ggml-large-v3-turbo-q5_0.bin", "ggml-large-v3-turbo-encoder.mlmodelc.zip"):
    hf_hub_download(
        "ggerganov/whisper.cpp", name,
        revision="5359861c739e955e79d9a303bcbc70fb988958b1",
        local_dir=".local/native",
    )
PY
unzip -q .local/native/ggml-large-v3-turbo-encoder.mlmodelc.zip -d .local/native
```

For Metal, start a Metal-enabled, Core-ML-disabled `whisper-server` in another terminal. The tested binary was Homebrew whisper-cpp 1.8.4; confirm `COREML = 0` in its log. Bind only to loopback:

```sh
whisper-server -m .local/native/ggml-large-v3-turbo-q5_0.bin \
  --host 127.0.0.1 --port 18766 -bo 1 -bs 1 -nt -nlp -t 4
```

Run the first comparison and whole-utterance control:

```sh
uv run --frozen python scripts/benchmark_backends.py \
  --fixtures .local/backend-fixtures/manifest.json --repeats 3 \
  --native-label cpp-metal --output .local/backend-results/asr-3s.json
uv run --frozen python scripts/benchmark_backends.py \
  --fixtures .local/backend-fixtures/manifest.json --repeats 2 --whole-utterance \
  --native-label cpp-metal --output .local/backend-results/asr-whole.json
```

Stop the Metal server before testing Core ML. The tested Core ML build reused Homebrew GGML 0.11.0 and disabled fallback. With that dependency and CMake installed:

```sh
git clone --depth 1 --branch v1.8.4 https://github.com/ggml-org/whisper.cpp .local/native/whisper.cpp
cmake -S .local/native/whisper.cpp -B .local/native/build-coreml \
  -DCMAKE_BUILD_TYPE=Release -DWHISPER_COREML=ON \
  -DWHISPER_COREML_ALLOW_FALLBACK=OFF -DWHISPER_USE_SYSTEM_GGML=ON \
  -DCMAKE_PREFIX_PATH=/opt/homebrew/opt/ggml \
  -DCMAKE_CXX_FLAGS=-I/opt/homebrew/opt/ggml/include \
  -DCMAKE_EXE_LINKER_FLAGS=-L/opt/homebrew/opt/ggml/lib \
  -DCMAKE_SHARED_LINKER_FLAGS=-L/opt/homebrew/opt/ggml/lib \
  -DWHISPER_BUILD_TESTS=OFF -DWHISPER_BUILD_SERVER=ON
cmake --build .local/native/build-coreml --target whisper-server -j4
.local/native/build-coreml/bin/whisper-server \
  -m .local/native/ggml-large-v3-turbo-q5_0.bin \
  --host 127.0.0.1 --port 18766 -bo 1 -bs 1 -nt -nlp -t 4
```

Confirm the Core ML encoder loaded, then run in another terminal:

```sh
uv run --frozen python scripts/benchmark_backends.py \
  --fixtures .local/backend-fixtures/manifest.json --repeats 3 \
  --native-label cpp-coreml --output .local/backend-results/asr-coreml-3s.json
uv run --frozen python scripts/benchmark_backends.py \
  --fixtures .local/backend-fixtures/manifest.json --mode realtime --repeats 2 \
  --native-label cpp-coreml --output .local/backend-results/realtime-coreml-3s.json
```

`--backend mlx` runs only the current backend; `--native-provenance PATH` embeds a caller-supplied JSON build/model record. The native label is descriptive, not automatic backend detection: retain startup logs to verify it. Raw reports contain transcripts and translations under ignored `.local`; review/redact before sharing. Reporting unit tests check error accounting and endpoint restrictions without loading models; they are not performance evidence.

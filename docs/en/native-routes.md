[English](../en/native-routes.md) · [简体中文](../zh-CN/native-routes.md) · [Index](README.md)

# Swift and Rust component pilots — 2026-10-03

Neither tested route warrants replacing the default backend for speed. WhisperKit's tested compressed Turbo configuration was slower than MLX on this Mac. Moving the existing translation weights to MLX Swift gave no consistent gain. Rust calling whisper.cpp reproduced the earlier Core ML result, while its llama.cpp translation configuration was slower. Translation content checks also failed, including on the current Python baseline.

This extends the [first backend pilot](backend-pilot.md). [Sanitized measurements](../benchmarks/native-routes-2026-10-03.json) contain six experiments and 272 utterance/backend runs, including diagnostic configurations. There are still only **eight distinct speech samples**. Raw audio and model output remain in ignored `.local`.

## What was actually tested

The machine, source fixtures, production code and WER/CER rules are unchanged from the first pilot. Each comparison alternates backend order over three repeats after English/Japanese warm-up; the whole-utterance control has two repeats. Builds completed before measurement, and no two inference jobs ran concurrently. Idle native servers remained loaded.

- **Swift ASR:** a resident release-build worker calls open-source [WhisperKit](https://github.com/argmaxinc/argmax-oss-swift), with `large-v3-v20240930_626MB`. The Core ML compute configuration is CPU/GPU for mel features and CPU/NeuralEngine for encoder/decoder; actual device utilization was not profiled. Greedy decoding, fixed language, 128-token limit, no timestamps, no temperature retries, one worker.
- **Swift translation:** a resident release-build worker loads the **same local MLX Qwen2.5-3B 4-bit snapshot** through [MLX Swift LM](https://github.com/ml-explore/mlx-swift-lm). It uses synchronous full-output generation; no first-Chinese streaming claim is made.
- **Rust:** a resident release-build program uses loopback HTTP to call the previously tested whisper.cpp Core ML server and a Metal-enabled [llama.cpp](https://github.com/ggml-org/llama.cpp) server with official Qwen2.5-3B-Instruct Q4_K_M GGUF. Rust orchestrates requests; C/C++ libraries perform inference. This is not a measurement of pure Rust inference or isolated Rust scheduling overhead.
- **Harness:** Python supplies identical inputs, the existing segmentation and scoring. Native ASR timings include JSON-line IPC and WAV file I/O; Rust timings additionally include HTTP. This is **not** a completed native subtitle service, browser test or combined first-Chinese latency benchmark.
- **Translation control:** whole reference transcripts bypass ASR. Every backend receives exactly the production prompt token IDs, temperature 0 and a 256-token cap. GGUF tokenization was checked against MLX before reusing IDs. All requests start with fresh KV caches; this compares full translation calls without production prefix-cache reuse. Different generated text/token counts affect latency. These numbers cannot be directly compared with the shorter, cached segments in the first pipeline replay.

Swift 6.4, Cargo/Rust toolchain 1.88.0; Swift/Rust dependency locks are committed. Library commits, model revisions, GGUF hash and the previous Python environment are in the numeric artifact. WhisperKit Core ML, GGML Q5_0 and MLX 4-bit ASR weights are different artifacts; Q4_K_M and MLX 4-bit translation weights also differ. Only the Swift/Python translation comparison reuses the exact weight files. Model license obligations remain as documented in [models](models.md).

## Recognition results

P50 / P95 in milliseconds, including all returned calls. Each backend has 33 English and 24 Japanese segment calls. WER/CER retain missing output.

| Comparison | Backend | English ASR | Japanese ASR | Accepted / total | English WER | Japanese CER |
| --- | --- | --- | --- | --- | --- | --- |
| Swift | MLX baseline | 489.72 / 507.40 | 492.62 / 512.82 | 57 / 57 | 5.71% | 31.52% |
| Swift | WhisperKit, aligned filtering | 693.35 / 718.55 | 710.23 / 773.45 | 57 / 57 | 7.14% | 45.65% |
| Rust | MLX baseline | 490.52 / 497.21 | 492.47 / 505.26 | 57 / 57 | 5.71% | 31.52% |
| Rust | Rust → whisper.cpp Core ML | 478.71 / 498.53 | 486.11 / 503.30 | 54 / 57 | 7.14% | 30.43% |

Rust's missing three results are the same Japanese short tail rejected as low confidence once per repeat. There were no inference exceptions. WhisperKit was about 42–44% slower in median call duration in this configuration; this is not a claim about every WhisperKit model or compute setting.

The initial WhisperKit configuration retained its extra first-token/silence gates and returned 3 empty English and 9 empty Japanese segments; Japanese CER was 46.74%. To avoid attributing these configuration differences to Swift, the main comparison disables WhisperKit's internal gates and applies TingSub's existing post-decode filter to returned metadata. The complete diagnostic run is retained as `phase2-swift-asr-default-gates`. Confidence normalization still differs across libraries. Disabling gates recovered output, but did not eliminate short-tail hallucinations.

The whole-utterance control reduced WhisperKit Japanese CER from 45.65% to **3.26%** across the four Japanese clips (MLX: 31.52% to 4.35%). English whole-utterance WER was 4.29% for both. That supports investigating boundary context; it does not justify waiting for full sentences in a live product. Whole-utterance median ASR was 740 ms English / 775 ms Japanese for WhisperKit versus 511 / 511 ms for MLX, excluding the time spent collecting the utterance.

## Translation results and failed content checks

P50 / P95 full-translation milliseconds, 12 calls per language per backend. All outputs passed JSON/field parsing; **this is not a translation-quality pass**.

| Comparison | Backend | English → Chinese | Japanese → Chinese + English |
| --- | --- | --- | --- |
| Swift | Python MLX | 317.66 / 542.72 | 423.19 / 534.60 |
| Swift | MLX Swift | 327.50 / 550.21 | 493.68 / 550.30 |
| Rust | Python MLX | 319.76 / 544.02 | 423.15 / 535.37 |
| Rust | Rust → llama.cpp Q4_K_M | 360.34 / 571.31 | 552.96 / 602.15 |

The existing meeting-fixture content requirements were applied to the saved real outputs: preserve meeting, three o'clock and bringing a computer, without inventing a day period. English TTS passed in all three repeats for every backend. **Japanese TTS failed in all three repeats for every backend**:

- Python MLX and MLX Swift put an English meeting/time sentence inside the `zh` field, leaving the required Chinese meeting/time content absent.
- llama.cpp returned Chinese meeting/time content, but added **“3 p.m.”** to the English translation even though the Japanese source does not specify afternoon.

These are whole-reference-text translation reproductions, not proof that every live segmented rendering has the same error. No general human translation score was calculated for the six read-speech references. The final harness records content failures separately and exits nonzero for inference, JSON or checked-content failures; valid JSON is never counted as a semantic acceptance result. Reporting unit tests do not perform inference and are not performance evidence.

## Reproduce

Run commands from the repository root. First prepare the MLX models and the same fixtures using the [first pilot](backend-pilot.md). Use the tested toolchains or record differences. The Swift package requires Swift 6.2+; this run used Swift 6.4 with the Xcode build integration, including Metal resources. On older SwiftPM setups, follow MLX Swift's Xcode build instructions if Metal resources cannot be built. No signed app, installer, Linux/Windows port or browser integration is included.

Download the additional pinned artifacts:

```sh
uv run --frozen python - <<'PY'
from huggingface_hub import snapshot_download, hf_hub_download
snapshot_download(
    "argmaxinc/whisperkit-coreml", revision="0f63a7800b00dd0226abd051b906c246e1907482",
    allow_patterns=["openai_whisper-large-v3-v20240930_626MB/*"],
    local_dir=".local/native/whisperkit-models",
)
snapshot_download(
    "openai/whisper-large-v3-turbo", revision="41f01f3fe87f28c78e2fbf8b568835947dd65ed9",
    allow_patterns=["tokenizer.json", "tokenizer_config.json", "special_tokens_map.json",
                    "added_tokens.json", "vocab.json", "merges.txt", "config.json"],
    local_dir=".local/native/whisperkit-tokenizer",
)
hf_hub_download(
    "Qwen/Qwen2.5-3B-Instruct-GGUF", "qwen2.5-3b-instruct-q4_k_m.gguf",
    revision="7dabda4d13d513e3e842b20f0d435c732f172cbe", local_dir=".local/native",
)
PY
swift build --package-path experiments/native-swift -c release --product ASRPilot -j 4
swift build --package-path experiments/native-swift -c release --product TranslationPilot -j 4
cargo build --manifest-path experiments/native-rust/Cargo.toml --release --locked
```

Build the pinned llama.cpp server:

```sh
git clone https://github.com/ggml-org/llama.cpp .local/native/llama.cpp
git -C .local/native/llama.cpp checkout b92761a515ea31e852e7fbc1fad5f874b46f3718
cmake -S .local/native/llama.cpp -B .local/native/build-llama \
  -DCMAKE_BUILD_TYPE=Release -DLLAMA_BUILD_TESTS=OFF \
  -DLLAMA_BUILD_EXAMPLES=OFF -DLLAMA_BUILD_SERVER=ON -DGGML_METAL=ON -DGGML_NATIVE=ON
cmake --build .local/native/build-llama --target llama-server -j4
.local/native/build-llama/bin/llama-server \
  -m .local/native/qwen2.5-3b-instruct-q4_k_m.gguf \
  --host 127.0.0.1 --port 18767 -ngl 99 -c 2048 -np 1 -t 4 --no-webui
```

For Rust ASR, also start the first pilot's Core ML whisper-server on `127.0.0.1:18766`. Swift does not require those HTTP services. Stop other model sessions and wait for builds to finish before benchmarking. Run each command separately; translation content failures are expected with the recorded models and should be investigated, not suppressed:

```sh
uv run --frozen python scripts/benchmark_native_routes.py --mode asr --route swift \
  --output .local/backend-results/swift-asr.json
uv run --frozen python scripts/benchmark_native_routes.py --mode asr --route rust \
  --output .local/backend-results/rust-asr.json
uv run --frozen python scripts/benchmark_native_routes.py --mode translation --route swift \
  --output .local/backend-results/swift-translation.json
uv run --frozen python scripts/benchmark_native_routes.py --mode translation --route rust \
  --output .local/backend-results/rust-translation.json
```

`--whole-utterance --repeats 2` selects the ASR control; `--whisperkit-default-gates` reproduces the original Swift filtering experiment. Workers remain loaded during a comparison and are closed afterward. Stop the two manually launched servers when finished. Runtime logs and reports can contain transcripts/private paths; only the explicitly sanitized numeric artifact is published.

The current decision is to retain MLX, improve segment context and translation acceptance, and reserve a Swift app or Rust service migration for a separately demonstrated packaging/platform need. This pilot does not establish a native-route latency advantage.

[English](../en/native-routes.md) · [简体中文](../zh-CN/native-routes.md) · [Index](README.md)

# Swift 与 Rust 组件实测 — 2026-10-03

本轮两条路线都不足以支持为了速度替换默认后端。在这台 Mac 上，所测 WhisperKit 压缩版 Turbo 配置比 MLX 慢；现有翻译权重迁到 MLX Swift 后也没有稳定收益。Rust 调用 whisper.cpp 基本复现了上一轮 Core ML 的结果，而 llama.cpp 翻译配置更慢。此外，翻译内容检查未通过，当前 Python 基线也存在同类问题。

这是[第一轮后端实测](backend-pilot.md)的后续。[脱敏数值记录](../benchmarks/native-routes-2026-10-03.json)包含 6 组实验、272 次音频／后端运行，含诊断配置；不同语音样本仍只有 **8 条**。音频和模型原始输出仅保留在被忽略的 `.local`。

## 实际测试了什么

机器、音频、生产代码及 WER/CER 规则沿用第一轮。英日预热后，每组对比执行 3 轮并交替后端顺序；整句对照执行 2 轮。测量前已完成构建，推理任务没有并发运行，空闲的原生服务保持加载。

- **Swift 识别：**常驻的 Release 构建程序调用开源 [WhisperKit](https://github.com/argmaxinc/argmax-oss-swift)，模型为 `large-v3-v20240930_626MB`。Core ML 配置为 mel 特征使用 CPU/GPU，编码器与解码器使用 CPU/NeuralEngine；没有测量实际计算单元使用率。固定语言、贪心解码、最多 128 个 token、无时间戳、不重试温度、单 worker。
- **Swift 翻译：**常驻的 Release 构建程序通过 [MLX Swift LM](https://github.com/ml-explore/mlx-swift-lm) 加载**现有同一份 MLX Qwen2.5-3B 4-bit 本地权重**。使用同步完整输出调用，不宣称测到了流式首中。
- **Rust：**常驻的 Release 构建程序通过本机 HTTP 调用上一轮的 whisper.cpp Core ML 服务，以及启用 Metal 的 [llama.cpp](https://github.com/ggml-org/llama.cpp) 服务；后者使用官方 Qwen2.5-3B-Instruct Q4_K_M GGUF。Rust 负责请求调度，C/C++ 库执行模型推理，本轮没有单独量化 Rust 调度开销。
- **测试驱动：**Python 提供相同输入、现有切段和评分。原生识别耗时包含 JSON 行协议通信及 WAV 文件读写，Rust 还包含 HTTP。这里**没有完成原生字幕服务、浏览器测试或整条链路首中测试**。
- **翻译控制条件：**使用完整参考文本，绕过语音识别。所有后端接收生产代码生成的相同提示词 token，温度 0、最多生成 256 个 token；复用 token 前核对了 GGUF 与 MLX 的分词结果。每次请求均从空 KV 缓存开始，没有复用生产链路的提示前缀缓存。输出文字和 token 数不同会改变耗时；本轮数字不能直接与第一轮较短、带缓存的切段翻译耗时比较。

实测 Swift 6.4、Cargo/Rust 工具链 1.88.0，提交了两边的依赖锁文件。库提交、模型版本、GGUF 哈希及 Python 环境见数值记录。WhisperKit Core ML、GGML Q5_0、MLX 4-bit 识别权重不是相同文件；Q4_K_M 与 MLX 4-bit 翻译权重也不同。只有 Swift/Python 翻译对比复用了完全相同的权重文件。[模型许可](models.md)要求不因更换服务语言而改变。

## 识别结果

下表为 P50 / P95 毫秒，包含所有正常返回的调用。每个后端有 33 次英文、24 次日文片段调用；WER/CER 包含缺失输出。

| 对比组 | 后端 | 英文识别 | 日文识别 | 接受 / 总片段 | 英文 WER | 日文 CER |
| --- | --- | --- | --- | --- | --- | --- |
| Swift | MLX 基线 | 489.72 / 507.40 | 492.62 / 512.82 | 57 / 57 | 5.71% | 31.52% |
| Swift | WhisperKit，统一过滤 | 693.35 / 718.55 | 710.23 / 773.45 | 57 / 57 | 7.14% | 45.65% |
| Rust | MLX 基线 | 490.52 / 497.21 | 492.47 / 505.26 | 57 / 57 | 5.71% | 31.52% |
| Rust | Rust → whisper.cpp Core ML | 478.71 / 498.53 | 486.11 / 503.30 | 54 / 57 | 7.14% | 30.43% |

Rust 缺失的 3 个结果，仍是同一日语短尾每轮被低置信度过滤一次。没有推理异常。所测 WhisperKit 配置的识别中位耗时慢约 42–44%，不能据此概括它的全部模型与计算配置。

WhisperKit 最初保留自身额外的首 token／静音判断，返回了 3 个英文空片段和 9 个日文空片段，日语 CER 为 46.74%。为避免把配置差异归因于 Swift，正式对比关闭其内部判断，再对返回的元数据应用 TingSub 现有解码后过滤。原始实验完整保留为 `phase2-swift-asr-default-gates`；不同库的置信度归一化仍有差异。关闭额外判断恢复了输出，却没有消除短尾幻觉。

整句对照中，4 条日语音频的 WhisperKit CER 从 45.65% 降到 **3.26%**；MLX 从 31.52% 降到 4.35%。英文整句 WER 两边均为 4.29%。这支持继续研究跨切段上下文，但不代表直播应该等待整句。WhisperKit 整句识别中位耗时约英文 740 ms／日文 775 ms，MLX 约 511／511 ms；这里还没算等待整句话的时间。

## 翻译耗时与未通过的内容检查

下表为完整翻译 P50 / P95 毫秒，每个后端、每种语言 12 次调用。所有输出通过了 JSON／字段解析，**不等于翻译质量通过**。

| 对比组 | 后端 | 英文 → 中文 | 日文 → 中英双语 |
| --- | --- | --- | --- |
| Swift | Python MLX | 317.66 / 542.72 | 423.19 / 534.60 |
| Swift | MLX Swift | 327.50 / 550.21 | 493.68 / 550.30 |
| Rust | Python MLX | 319.76 / 544.02 | 423.15 / 535.37 |
| Rust | Rust → llama.cpp Q4_K_M | 360.34 / 571.31 | 552.96 / 602.15 |

对已保存的真实输出，沿用原有会议冒烟用例的内容要求：保留会议、三点、携带电脑，不擅自增加上午／下午。英文 TTS 在所有后端的 3 轮中均通过；**日文 TTS 在所有后端的 3 轮中均未通过**：

- Python MLX 与 MLX Swift 把英文的会议／时间句子放进 `zh` 字段，缺少要求保留的中文会议和时间信息。
- llama.cpp 的中文字段保留了会议和时间，但英文增加了 **“3 p.m.”**，而日文原文没有说明下午。

这是完整参考文本输入时的翻译问题复现，不代表每次直播切段渲染都会发生同样错误。6 条朗读参考文本没有进行通用人工翻译评分。最终脚本分别记录内容失败，并在推理、JSON 或已检查内容失败时以非零状态退出；JSON 合法不会被当成语义验收通过。报告统计单测不执行模型，也不作为性能证据。

## 复现方法

在仓库根目录执行命令。先按[第一轮报告](backend-pilot.md)准备 MLX 模型和相同音频。使用实测工具链或记录差异。Swift 包要求 Swift 6.2+；本轮使用 Swift 6.4 的 Xcode 构建集成，包含 Metal 资源。旧版 SwiftPM 若无法生成 Metal 资源，应参照 MLX Swift 的 Xcode 构建说明。本轮不包含签名应用、安装器、Linux/Windows 移植或浏览器集成。

下载额外的固定版本模型：

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

构建固定提交的 llama.cpp 服务：

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

测试 Rust 识别还需按第一轮说明在 `127.0.0.1:18766` 启动 Core ML whisper-server；Swift 不依赖这两个 HTTP 服务。停止其他模型会话，等待构建完成后再测。以下命令分别执行；记录中的模型预计会触发翻译内容失败，应保留并分析，不能忽略：

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

`--whole-utterance --repeats 2` 选择整句识别对照；`--whisperkit-default-gates` 复现最初的 Swift 过滤配置。对比期间 worker 常驻，结束后关闭；手动启动的两个服务需在测试结束后停止。运行日志与原始报告可能含转写和私人路径，公开的仅为显式脱敏后的数值记录。

当前继续保留 MLX，优先改进切段上下文和翻译验收。Swift 应用或 Rust 服务迁移，应由明确的安装交付／平台需求另行驱动，本轮没有证明原生路线带来延迟优势。

[English](../en/backend-pilot.md) · [简体中文](../zh-CN/backend-pilot.md) · [Index](README.md)

# 本地后端小样本实测 — 2026-10-03

暂时保留当前 MLX 后端。在这台机器和这批小样本上，whisper.cpp Metal 的识别中位耗时慢约 20%；Core ML 版本的纯识别中位耗时只改善 1.6–1.9%，加入翻译后也没有稳定收益。这些结果不足以支持把 Python 服务重写成原生程序。更值得继续处理的是强制切段导致的识别错误。

本轮仅新增可选实验脚本，没有修改服务、扩展或默认配置。[数值记录](../benchmarks/backend-pilot-2026-10-03.json) 包含各轮计数、每条音频的编辑距离、耗时、模型版本及音频哈希。音频、参考文本、模型输出和私人路径仅保留在本地。

## 环境与证据范围

- Apple M4 Pro、48 GB 内存、macOS 27.0.1、Python 3.12.11；生产代码提交为 `eda8e783f916c52239cfe6966439478045421b6f`。
- MLX 0.32.3、mlx-whisper 0.4.3、mlx-lm 0.32.0。原生侧为 whisper.cpp 1.8.4（`9386f239401074690479731c1e41683fbbeac557`）、系统 GGML 0.11.0、4 个 CPU 线程、贪心解码。Python 依赖由锁文件固定。
- 同属 Whisper large-v3-turbo，但 **MLX 4-bit 与 GGML Q5_0 的权重和量化格式不同**；Core ML 还使用独立的已编译编码器。解码细节与置信度计算也有差异。本轮比较的是可部署配置，不能单独归因于 Python 解释器开销。
- 两边共用现有 MLX Qwen2.5-3B-Instruct-4bit 翻译器，固定输入语言，输出中英双语，关闭草稿，使用现有 VAD 和最长 3 秒切段。每条音频开始前清空翻译历史。
- 8 条不同音频，共 43.857 秒：英文 [LibriSpeech dummy](https://huggingface.co/datasets/hf-internal-testing/librispeech_asr_dummy) 数据集查看器前 3 行、日文 [JSUT](https://huggingface.co/datasets/japanese-asr/ja_asr.jsut_basic5000) 前 3 行，以及 2 条 macOS 合成语音。真人录音是**朗读语音**，不是嘈杂直播；选样发生在查看识别结果之前。数据版本与哈希见数值记录。本仓库不重新分发原始音频，复用前请查看来源的使用条款。
- 每个后端分别用英日真实音频预热，轮次之间交替执行顺序。切段识别测 3 轮；整句对照及定速回放测 2 轮。重复同一音频不增加独立语料数量。模型加载和识别预热不进入延迟统计；翻译没有单独预热轮次。
- 纯识别模式预先切段，再计时真实调用。定速回放每 20 ms 投递 PCM 帧，经过真实 `Segmenter` 与 `Pipeline`，包含 VAD 等待、调度、识别与翻译。原生侧还包含本机 HTTP/WAV 传输。**未测浏览器采集、WebSocket 传输或浮层渲染。**
- Core ML 构建关闭失败回退，启动日志确认加载了编码器；这不代表已确认每项运算在哪个 Apple 计算单元执行，本轮没有测量 ANE 使用率。也未测功耗、峰值内存、长时间稳定性、自动语言识别或人工翻译质量。测试在正常桌面环境进行，不是隔离的性能实验室。

## 纯识别耗时

下表为 P50 / P95，单位毫秒。每组对比中，每个后端有 33 次英文、24 次日文片段调用。所有正常返回的识别调用，包括结果被拒绝的调用，都计入本表耗时。

| 对比组 | 后端 | 英文 | 日文 | 有识别结果 / 总片段 |
| --- | --- | --- | --- | --- |
| Metal | MLX | 487.70 / 497.55 | 494.77 / 503.70 | 57 / 57 |
| Metal | whisper.cpp Metal | 584.90 / 591.91 | 590.81 / 604.13 | 57 / 57 |
| Core ML | MLX，同轮重新测量 | 488.32 / 495.12 | 491.43 / 499.29 | 57 / 57 |
| Core ML | whisper.cpp Core ML | 479.30 / 488.17 | 483.54 / 496.91 | 54 / 57 |

Core ML 在 3 轮中均因低置信度拒绝了同一个日语尾片段。没有推理异常。识别覆盖率或质量发生变化时，单看耗时不足以判断改进。

## 定速回放：识别与翻译

以下为 MLX/Core ML 交替执行、各 2 轮的结果。“首中”从**每个片段**的首个人声帧计时，“句尾”从最后人声帧计时，两者都不是整条录音的启动耗时。数值为 P50 / P95 毫秒，**仅统计成功翻译的片段**。其他计数为零，没有积压丢弃或推理异常。

| 后端 / 语言 | 翻译成功 / 片段数 | 低置信度 | 首中 | 句尾 | 识别 | 翻译 |
| --- | --- | --- | --- | --- | --- | --- |
| MLX / 英文 | 22 / 22 | 0 | 3112 / 3753 | 867 / 1067 | 528 / 539 | 179 / 330 |
| Core ML / 英文 | 22 / 22 | 0 | 3092 / 3759 | 846 / 1047 | 488 / 559 | 188 / 336 |
| MLX / 日文 | 16 / 16 | 0 | 2812 / 3707 | 1028 / 1372 | 524 / 545 | 265 / 507 |
| Core ML / 日文 | 14 / 16 | 2 | 3503 / 3751 | 993 / 1435 | 518 / 577 | 415 / 522 |

英文首中中位值只差 20 ms。日语两边进入统计的片段不同，识别文本不同也会改变翻译工作量，不能据此直接给后端排速度名次。数值记录另保留了一轮较早的 MLX 单独回放作为初步基线；正式对比使用上表的交替执行结果。

## 切段对质量的影响

英文采用词编辑距离计算总体词错率 WER，日文采用字符编辑距离计算总体字符错率 CER。归一化包括 NFKC、转小写、删除标点和符号、处理空白；不合并日文汉字／假名写法，也不合并阿拉伯数字与文字数字。缺失输出仍计入分母，整条缺失按全部删除计错。这是识别评分，不是翻译评分。

| 输入方式 | 后端 | 英文 WER，4 条音频 | 日文 CER，4 条音频 |
| --- | --- | --- | --- |
| 3 秒切段 | MLX | 5.71% | 31.52% |
| 3 秒切段 | whisper.cpp Metal | 7.14% | 31.52% |
| 3 秒切段 | whisper.cpp Core ML | 7.14% | 30.43% |
| 整句离线对照 | MLX | 4.29% | 4.35% |
| 整句离线对照 | whisper.cpp Metal | 4.29% | 3.26% |

仅看 **3 条真人日语朗读**，切段后 MLX 与 Metal 都是 28 次编辑 / 65 个参考字符，CER 为 43.08%；整句识别后，MLX 为 3 / 65（4.62%），Metal 为 2 / 65（3.08%）。极短的尾片段有时会识别出无关的结束致谢，置信度过滤没有拦住所有幻觉。

这复现了值得处理的故障，但不是有代表性的日语准确率评测。等待整句结束不是拟采用的直播方案：其中一条英文音频长达 12.485 秒。下一步应试验跨边界保留识别上下文、提交稳定文本，同时避免重复或删词，再用更大语料与真实浏览器会话比较质量和延迟。现有结果不支持直接缩短片段来追求低延迟。

## 本地复现

在 Apple Silicon Mac 上按[安装指南](installation.md)准备模型，停止其他字幕／模型会话，安装 `ffmpeg`、macOS Samantha/Kyoko 语音及 whisper.cpp 1.8.4。只有准备阶段下载资源，推理全程在本地进行；请为原生权重、编码器和构建预留磁盘空间。

```sh
uv sync --frozen
uv run --frozen python scripts/prepare_backend_fixtures.py
```

脚本读取数据集查看器当前行。复测时先对照已发布记录，确认生成的清单版本与哈希相同；操作系统和 ffmpeg 版本可能改变 TTS 或转换产物。保留 `.local/backend-fixtures`，多轮使用同一批输入。

下载固定版本的原生权重：

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

先在另一终端启动启用 Metal、关闭 Core ML 的 `whisper-server`。实测使用 Homebrew whisper-cpp 1.8.4；请从日志确认 `COREML = 0`。只绑定本机回环地址：

```sh
whisper-server -m .local/native/ggml-large-v3-turbo-q5_0.bin \
  --host 127.0.0.1 --port 18766 -bo 1 -bs 1 -nt -nlp -t 4
```

执行第一组对比与整句对照：

```sh
uv run --frozen python scripts/benchmark_backends.py \
  --fixtures .local/backend-fixtures/manifest.json --repeats 3 \
  --native-label cpp-metal --output .local/backend-results/asr-3s.json
uv run --frozen python scripts/benchmark_backends.py \
  --fixtures .local/backend-fixtures/manifest.json --repeats 2 --whole-utterance \
  --native-label cpp-metal --output .local/backend-results/asr-whole.json
```

测 Core ML 前先停止 Metal 服务。实测的 Core ML 构建复用 Homebrew GGML 0.11.0，并关闭失败回退；安装该依赖及 CMake 后运行：

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

确认启动日志显示 Core ML 编码器已加载，再到另一终端运行：

```sh
uv run --frozen python scripts/benchmark_backends.py \
  --fixtures .local/backend-fixtures/manifest.json --repeats 3 \
  --native-label cpp-coreml --output .local/backend-results/asr-coreml-3s.json
uv run --frozen python scripts/benchmark_backends.py \
  --fixtures .local/backend-fixtures/manifest.json --mode realtime --repeats 2 \
  --native-label cpp-coreml --output .local/backend-results/realtime-coreml-3s.json
```

`--backend mlx` 只运行当前后端；`--native-provenance PATH` 可嵌入调用方提供的 JSON 构建／模型记录。后端标签只是描述，不会自动探测，请保留启动日志核验。原始报告包含转写和译文，位于被忽略的 `.local`，分享前请检查并脱敏。报告统计单测只验证失败计数与地址限制，不加载模型，也不作为性能证据。

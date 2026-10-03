[English](../en/benchmarks.md) · [简体中文](../zh-CN/benchmarks.md) · [Index](README.md)

# 性能与验证

## 指标含义

| 指标 | 定义 |
| --- | --- |
| 本段首字 | 本片段 VAD 首个人声到首次识别文本 |
| 首中 | 本片段 VAD 首个人声到首个完整中文文本 |
| 句尾 | 本片段 VAD 最后人声到完整双语结果 |
| 识别 | 语音识别调用耗时 |
| 翻译 | 翻译调用耗时，包含中文先行发送 |
| 排队 | 从任务入队到开始推理的单调时钟耗时 |

浮层测量接收／显示侧时间，服务端在发送前计算指标，两者会有少量差异。强制切段后重新计时，不等于自然整句重新开始。草稿设置会影响首字及 GPU 竞争。VAD 语音边界是估计值，不是人工标注的声学真值。

会话计数包括最终片段、成功翻译、低置信度、重复异常、无人声／空结果、跳过与错误。P50/P95 仅统计最近最多 **256 个成功翻译片段**；拒绝、过期和错误片段不进入分布，发布指标时必须同时提供对应计数。错误计数还可能包含草稿失败，不能直接当作互斥的最终片段失败率。

## 可复现冒烟测试

在 Apple Silicon Mac 上准备模型、安装 macOS 的 Samantha（英语）与 Kyoko（日语）语音，并启动服务。先停止其他字幕会话。

```sh
uv run --frozen python scripts/benchmark.py
uv run --frozen python scripts/benchmark.py --auto-language --no-partials
npm ci
npx playwright install chromium
npm run test:live
```

`benchmark.py` 用 macOS `say` 合成语音，以 20 ms 节奏发送到真实服务，断言保留关键内容：会议、三点、携带电脑，且不凭空增加上午／下午。它生成测试音频，并写入 `.local/benchmark/results-partials.json` 或 `results-no-partials-auto.json`。

`test:live` 需要已生成的测试音频和使用同一 `.local/token` 的运行中服务。它在独立 Chromium 播放音频，真实经过 tabCapture → AudioWorklet → WebSocket → MLX → 浮层。浏览器调试参数只用于可丢弃的测试配置，结果保存在 `.local/benchmark/browser-capture.json`。

直接模型检查需要**先停止服务**：

```sh
uv run --frozen python scripts/check_translation.py
uv run --frozen python scripts/check_streaming.py
uv run --frozen python scripts/compare_asr.py
```

它们分别检查短句翻译、中文先行与缓存隔离、旧新识别路径对比。模型缺失或断言不满足会失败，不会回退成假推理。模型上游版本及运行时变化可能改变输出。

## 证据范围

初始实现曾在 Apple M4 Pro、48 GB 内存机器上验证真实英日合成语音，包括浏览器音频采集链路；当时的模型提交见[模型说明](models.md)。本地原始录音、转写和机器相关日志不公开。请在自己的工作区重新运行；这些记录不构成可复现的公开评测数据集或 CI 性能承诺。

当前尚无获得授权的自然语音评测集、人工翻译评分、WER/CER 报告或长时间稳定性基准。合成语音冒烟测试证明特定内容通过了链路，不能证明自然直播鲁棒性。背景音乐、多人重叠、专有名词、极短语音及 3 秒边界切词仍是常见失败场景。

分享结果时请包含提交、芯片与内存、macOS/Chrome、模型版本、草稿／语言／显示设置、预热方式、样本数、全部拒绝／跳过／错误计数及 P50/P95。只使用有权分享的音频，删除配对码和私人路径。对比时使用同一音频与设置；漏掉更多语音造成的低延迟不算改进。

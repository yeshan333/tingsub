[English](../en/architecture.md) · [简体中文](../zh-CN/architecture.md) · [Index](README.md)

# 架构与协议

## 组件

| 文件 | 职责 |
| --- | --- |
| `extension/background.js` | 用户操作授权、当前标签页访问、offscreen 生命周期与消息路由 |
| `extension/offscreen.js` | 采集、原声回放、WebSocket 连接及停止清理 |
| `extension/pcm-worklet.js` | 单声道 PCM16 分帧与采集时间戳 |
| `extension/overlay.js` | Shadow DOM 字幕、过期结果抑制、全屏与交互 |
| `src/live_subs/audio.py` | VAD 分段与有界待处理队列 |
| `src/live_subs/server.py` | 本机服务、配对与单会话所有权 |
| `src/live_subs/pipeline.py` | 调度、中文先行事件、错误与指标 |
| `src/live_subs/engine.py` | MLX 本地识别、翻译、质量检查与提示缓存 |
| `src/live_subs/cli.py` | 模型准备、配对及服务启动 |

## 音频与调度

Chrome 仅采集选定标签页。一条原生采样率音频通路恢复原声回放，另由 AudioContext 重采样到 16 kHz。Worklet 对声道取平均，每 20 ms 输出 320 个 PCM16 采样点。输入通道缺失时输出静音，时间轴持续前进。

服务采用 RMS 门限与 WebRTC VAD，保留 200 ms 前置缓冲，约 240 ms VAD 静音后提交，或达到 3 秒最大片段时强制提交。VAD 的挂起时间会增加配置值之外的等待。可选草稿每 800 ms 尝试生成。强制切段后的短尾音会保留，独立的极短噪声会过滤。采集时间戳发生跳变时结束旧片段，避免拼接中断两侧的声音。

一个专用线程执行 MLX 推理。待处理队列最多保留三个最终片段和一个最新草稿，最终片段优先；等待时间或采集落后超过 2.5 秒的任务在推理前显式跳过。已经开始的 GPU 调用不会被强制中断，因此页面导航或断连后可能仍有短暂的在途推理。

Whisper 的语言识别和转写共享一次音频编码。重复异常或低置信度结果被拒绝。仅翻译最终片段：英语直接保留原文作为英文，日语双语结果先生成中文。完整中文 JSON 字符串解析成功即发送，再发送完整结果。提示缓存只复用确认一致的 token 前缀，不主动加入对话历史。字幕通过 `textContent` 渲染，不把模型文本当 HTML 执行。

## 本机协议（版本 1）

这是内部协议，并非稳定的第三方 API。含 `tingqiao` 的内部标识保留以兼容早期原型。

- `GET /health`：就绪状态、繁忙状态、`service: "tingqiao"`、`protocol: 1`；无需认证，不返回转写内容。
- `WS /stream`：检查扩展来源，5 秒内完成配对码握手。来源检查本身不等于认证。一次仅允许一个已认证流。
- 首条 JSON：`{"token":"<本机配对码>","language":"en","display":"zh-en","partials":true}`。语言为 `en`、`ja`、`auto`；显示模式为 `zh-en`、`source-zh`。
- 收到 `ready` 后发送二进制帧：小端 float64 帧结束 Unix 毫秒时间戳（8 字节），随后 320 个小端有符号 int16 采样（640 字节），合计 648 字节。
- `{"type":"ping"}` 返回 `pong`。`{"type":"stop"}` 提交尾段并处理待办，随后发送 `done`。直接断连取消等待中的任务，不保证排空。
- 服务事件：`ready`、`transcript`、`translation_progress`、`translation`、`rejected`、`dropped`、`notice`、`error`、`pong`、`done`。

字幕事件以片段 `id` 关联。`transcript` 包含 `source`、`language`、`final`、显示与时间字段；`translation_progress` 增加 `zh`；`translation` 增加完整 `zh`、`en`、推理耗时及指标。拒绝事件携带 `reason`，错误携带可读的 `message`。客户端必须忽略最终或翻译结果之后的旧草稿，以及超出历史窗口的结果。浮层只显示最新两个片段，15 秒无新字幕后清空。

指标包含会话累计计数，以及最近最多 256 个成功翻译片段的 P50/P95，见[指标定义](benchmarks.md)。协议变化需要同步升级扩展与服务。

## 功能边界

服务仅监听本机，运行期间无云端回退或模型下载。没有麦克风模式、字幕导出、多用户 API、持久化转写数据库、说话人分离或整句准确率保证。Apple MLX 之外的 GPU 后端需要单独实现并验证。

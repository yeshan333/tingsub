[English](../en/troubleshooting.md) · [简体中文](../zh-CN/troubleshooting.md) · [TingSub](../../README.zh-CN.md)

# 故障排查

| 现象 | 检查与处理 |
| --- | --- |
| 本机服务未就绪 | 在仓库根目录执行 `uv run --frozen tingsub serve`，等待预热完成。用 `curl http://127.0.0.1:18765/health` 检查；就绪服务返回 `service: tingqiao`、`protocol: 1`。`tingqiao` 是保留的内部协议标识。 |
| 配对码错误 | 在与服务相同的数据目录执行 `uv run --frozen tingsub pair`，替换弹窗中的配对码，再重新启动采集。不要把配对码贴到 issue。 |
| 端口占用 | 用 `lsof -nP -iTCP:18765 -sTCP:LISTEN` 查看。如果是另一份 TingSub，使用或停止那份服务；不要结束未知进程。只修改服务端口不会同步修改扩展。 |
| 模型缺失或下载失败 | 联网运行 `uv run --frozen tingsub prepare`，核对 `.local/models.json` 中的快照路径。下载中断可重试；仅在有意更新或修复模型时用 `--force`。启动服务不会补下载缺失文件。 |
| 已有其他连接 | 停止另一标签页或性能测试。一次只有一个连接拥有推理权。浏览器意外退出后等待断开；若持续繁忙则重启服务。 |
| 没声音或没字幕 | 确认选定标签页正在播放可听的人声且未静音，重新点击工具栏扩展按钮。请在普通网页启动，不要在 `chrome://` 或扩展页面启动。看弹窗是否收到音频；纯音乐可能被当作无人声或低置信度片段拒绝。 |
| 切换页面后字幕停止 | 属于预期行为，等待新页面加载后重新开始。 |
| 更新后仍残留旧浮层 | 在 `chrome://extensions` 重新加载扩展，刷新视频页面，再开始字幕。 |
| 字幕延迟或片段被跳过 | 固定输入语言、关闭草稿、停止其他 GPU 任务，再重新采集。3 秒片段仍需先收集音频；要同时观察首字、首中和句尾延迟。 |
| 识别错误或缺少字幕 | 背景音乐、多人重叠、专有名词、强制切段都是已知限制。关注拒绝计数；固定输入语言可以帮助选对语言，但不能保证准确率。 |
| 真实模型测试缺少 macOS 语音 | 在系统语音设置中安装 Samantha 和 Kyoko；`say -v '?'` 可列出已有语音。这些语音只用于测试。 |
| 修改依赖后 `npm ci` 失败 | 用 `npm install` 更新并检查 `package-lock.json`，再执行 `npm ci`。普通扩展使用者不需要 npm。 |

仍无法解决时，用中文或英文提交[问题报告](https://github.com/yeshan333/tingsub/issues/new?template=bug_report.yml)，附上 macOS、Chrome、芯片、内存、提交版本、设置、计数和最小复现步骤。请删去配对码、用户名、私人路径、音频和转写内容。漏洞请遵循[安全报告流程](../../SECURITY.zh-CN.md)。

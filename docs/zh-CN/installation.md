[English](../en/installation.md) · [简体中文](../zh-CN/installation.md) · [TingSub](../../README.zh-CN.md)

# 安装与使用

独立 App/DMG 用户不需要安装 Python 或 uv，直接按[桌面指南](desktop.md)操作；下方依赖和命令仅适用于源码安装。构建和签名方式见[分发指南](distribution.md)。

## 环境要求

- Apple Silicon（M 系列）Mac，macOS 14 或更新版本，建议 16 GB 及以上内存。
- Chrome 116+，允许加载已解压扩展。
- [uv](https://docs.astral.sh/uv/getting-started/installation/)，项目指定 Python 3.12。
- 安装依赖和首次从 Hugging Face 下载模型时需要网络。默认权重约 2.2 GB，另需依赖与缓存空间。
- 仅开发测试需要 Node.js 22+。

当前不支持 CPU、CUDA、Windows、Linux、Intel Mac 或 Firefox 运行后端。服务与 Chrome 必须运行在同一台 Mac 上。

## 使用桌面窗口

推荐通过 `uv run --frozen --extra desktop tingsub gui` 或 `gui.command` 打开桌面工作空间，在界面中准备模型、启动服务并复制配对码。完整说明见[桌面指南](desktop.md)。下方保留原有终端操作方式。

## 安装与启动

```sh
git clone https://github.com/yeshan333/tingsub.git
cd tingsub
uv sync --frozen --python 3.12
uv run --frozen tingsub prepare
uv run --frozen tingsub pair
uv run --frozen tingsub serve
```

`prepare` 将每个模型解析到具体的 Hugging Face 提交，并把本地快照信息写入 `.local/models.json`。已完整下载的快照会被复用。TingSub 不捆绑模型权重，请先阅读[模型许可](models.md)。

复制 `pair` 输出的配对码，等待 `Application startup complete`。首次加载和预热可能需要几十秒。保持终端运行，Ctrl+C 停止服务。

也可运行 `./setup.command` 安装依赖与模型，再运行 `./start.command` 显示配对码并启动服务。Finder 也能打开这些 `.command` 文件，具体取决于 Mac 的正常安全设置。

## 加载 Chrome 扩展并配对

1. 打开 `chrome://extensions`，开启开发者模式，点击**加载已解压的扩展程序**，选择 `tingsub/extension`。
2. 将 **TingSub · 听桥** 固定到工具栏。
3. 打开**本机配对**，在**配对码**里粘贴配对码。设置自动保存到当前浏览器的扩展本地存储中。
4. 打开正常的 HTTPS 视频网页并播放，点击**为当前标签页开启字幕**。

点击工具栏扩展按钮后才获得当前页面访问权限。Chrome 内部页面或禁止采集的页面无法生成字幕。插件不申请麦克风权限。

## 控件

| 控件 | 含义 |
| --- | --- |
| 直播语言 | 英语、日语或逐片段自动识别 |
| 字幕显示 | 中文＋英文，或中文＋原文 |
| 先显示识别草稿 | 提前显示可修订的原文，会增加识别次数及 GPU 负载 |
| 字幕字号 | 浮层字幕字体大小 |
| 本机配对／配对码 | 本地服务的连接凭据 |
| 停止 | 停止本次字幕采集 |

已知输入语言时直接选择，减少语言检测开销。GPU 负载较高时可关闭草稿。英语输入保留原文作为英文字幕；日语在中英模式下同时译成中文和英文。语言、显示模式、草稿及字号修改在下次启动采集时生效，请先停止再开始。

拖动字幕标题栏可移动浮层，网页全屏时会跟随进入。关闭弹窗不会停止采集；需点击弹窗的“停止”或浮层 ×。切换页面、刷新或关闭采集标签页会停止会话。服务一次仅处理一路直播。

## 本地文件与网络

从仓库根目录运行命令，默认数据目录相对于当前工作目录。`.local/token` 保存配对密钥；`.local/models.json` 指向 Hugging Face 缓存中的模型快照。使用 `tingsub --data-dir PATH pair` 和 `tingsub --data-dir PATH serve` 时，两个命令必须指定同一个目录。

扩展固定连接 **18765** 端口。虽然 CLI 提供 `serve --port`，但仅修改该参数会导致扩展无法连接，请使用默认端口。不要把服务公开监听或通过反向代理暴露到公网。

## 更新

先停止字幕和服务，在干净的工作区执行：

```sh
git pull --ff-only
uv sync --frozen
uv run --frozen tingsub serve
```

在 `chrome://extensions` 对 TingSub 点击**重新加载**，刷新视频页面，再开启字幕。模型版本默认不变；只有显式执行 `uv run --frozen tingsub prepare --force` 才会重新解析上游版本，可能改变质量、速度或许可信息。更新后请在本地核对 `.local/models.json`。

`live-subs` 保留为 `tingsub` 的兼容命令别名；Python 模块名仍为 `live_subs`，不影响仓库命名。

## 卸载

Ctrl+C 停止服务，在 `chrome://extensions` 移除扩展。不再需要时删除仓库及其中的 `.venv`、`.local`。模型快照单独保存在 Hugging Face 缓存中，可能被其他应用共享，请只删除确认不再使用的模型。项目不安装后台常驻守护进程或登录启动项。

桌面依赖更新请使用 `uv sync --frozen --extra desktop`。字幕设置共享与离线编辑行为见[桌面指南](desktop.md)。

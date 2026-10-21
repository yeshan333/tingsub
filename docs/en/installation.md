[English](../en/installation.md) · [简体中文](../zh-CN/installation.md) · [TingSub](../../README.md)

# Installation and usage

For the standalone desktop app, follow the [Release download instructions](distribution.md#download-a-release) and [desktop guide](desktop.md); no Python, uv or source checkout is required.

The requirements and instructions below apply strictly to **running from source**. Build and packaging workflows are documented in [distribution](distribution.md).

## Requirements

- Apple Silicon (M-series) Mac running macOS 14 or newer (16 GB RAM recommended).
- Chrome 116+ with permission to load unpacked extensions.
- [uv](https://docs.astral.sh/uv/getting-started/installation/) package manager (Python 3.12 pinned by the project).
- Internet connection for initial dependency installation and model downloads (default weights require about 2.2 GB, plus space for dependencies and caches).
- Node.js 22+ (only required for development tests).

There is currently no support for CPU, CUDA, Windows, Linux, Intel Mac, or Firefox. Both the background service and Chrome must run on the same Mac.

## Use the desktop window

Run `uv run --frozen tingsub gui` or open `gui.command` to prepare models, start the service and copy the pairing code in a desktop window. See the [desktop guide](desktop.md). The terminal workflow remains available below.

## Install and start

```sh
git clone https://github.com/yeshan333/tingsub.git
cd tingsub
uv sync --frozen --python 3.12
uv run --frozen tingsub prepare
uv run --frozen tingsub pair
uv run --frozen tingsub serve
```

`prepare` resolves each selected model to a concrete Hugging Face commit and records its local snapshot in `.local/models.json`. Existing complete snapshots are reused. It does not bundle model weights with TingSub. Read [model licenses](models.md) first.

Copy the code from `pair`. Wait for `Application startup complete`; model loading and warm-up can take tens of seconds on the first start. Keep this terminal running. Ctrl+C stops the service.

The equivalent convenience scripts are `./setup.command` (dependencies and models) and `./start.command` (show the pairing code, then serve). Finder can also open these `.command` files, subject to your Mac's normal security settings.

## Load and pair Chrome

1. In Chrome, navigate to `chrome://extensions` and enable **Developer mode** in the top-right corner.
2. Click **Load unpacked** and select the `tingsub/extension` directory from your checkout.
3. Pin **TingSub · 听桥** to your browser toolbar for easy access.
4. Click the TingSub toolbar icon, expand **本机配对** (Local pairing), and paste your pairing code into **配对码** (Pairing code). Settings save automatically to local extension storage.
5. Open a standard HTTPS video page playing audible speech, then click **为当前标签页开启字幕** (Start captions for this tab).

Clicking the extension icon grants access to the selected page; no microphone permission is ever requested. Internal Chrome URLs and pages blocking capture cannot be captioned.

## Controls

| Chinese label | Meaning |
| --- | --- |
| 直播语言 | Input: 英语 = English, 日语 = Japanese, 自动识别 = automatic detection |
| 字幕显示 | 中文＋英文 = Chinese + English; 中文＋原文 = Chinese + original transcript |
| 先显示识别草稿 | Show provisional source text; extra recognition work can increase GPU load |
| 字幕字号 | Caption font size |
| 本机配对 / 配对码 | Local pairing / pairing code |
| 停止 | Stop captions |

Select a known language to avoid language detection work. Turn drafts off if GPU contention is high. English speech uses the original transcript as its English caption; Japanese speech is translated to both Chinese and English in bilingual mode. Language/display/draft changes take effect on the next session; stop and start again. Font size applies on the next start too.

Drag the caption header to move the overlay. It follows webpage fullscreen. Closing the popup does not stop capture. Stop via the popup or overlay ×; navigation, reload and closing the captured tab stop the session. Only one stream can use the service at a time.

## Local files and networking

Run commands from the repository root: the default data directory is relative to the working directory. `.local/token` stores the pairing secret; `.local/models.json` records the snapshot paths. New downloads use TingSub’s private `.local/model-cache`, rather than the shared Hugging Face cache; other applications do not automatically reuse these files. Existing configurations may still point to the shared cache. With `--data-dir PATH`, new downloads use `PATH/model-cache`. `tingsub --data-dir PATH pair` and `tingsub --data-dir PATH serve` must use the same directory.

The extension expects port **18765**. Although the CLI exposes `serve --port`, changing only that option will break the extension connection; use the default port. Never expose this service on a public interface or through a reverse proxy.

## Update

Stop captions and the service. From a clean checkout, run:

```sh
git pull --ff-only
uv sync --frozen
uv run --frozen tingsub serve
```

Click **Reload** for TingSub in `chrome://extensions`, then refresh the video page and start captions again. Model versions remain unchanged unless explicitly refreshed with `uv run --frozen tingsub prepare --force`. That resolves current upstream revisions and can change quality, speed and license information; review the resulting `.local/models.json` locally.

`live-subs` remains a compatibility alias for `tingsub`. The Python module remains `live_subs`; neither affects the repository name.

## Uninstall

Stop the service with Ctrl+C, then remove the extension in `chrome://extensions`. Remove the checkout and its `.venv`/`.local` directories when no longer needed. New model downloads live in `.local/model-cache`, so deleting `.local` deletes those downloads too. Older configurations may still reference a shared Hugging Face cache: inspect `models.json` and only remove snapshots you no longer use. For the standalone App, follow the separate [uninstall steps](distribution.md). There is no installed background daemon or login item.

Use `uv sync --frozen` when updating desktop dependencies. See the [desktop guide](desktop.md) for shared preferences and offline editing behavior.

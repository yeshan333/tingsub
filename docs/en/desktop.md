[English](../en/desktop.md) · [简体中文](../zh-CN/desktop.md) · [Index](README.md)

# Desktop workspace

TingSub offers a lightweight macOS window using the system WebKit renderer. The Python/MLX service still performs inference in a separate process. The desktop interface is available in English and Simplified Chinese, with dark, light and system appearance.

![TingSub desktop interface, showing sample captions](../assets/desktop.png)

The caption preview uses authored sample text, not live transcription. Real captions appear on the selected browser page.

## Start

From an Apple Silicon checkout with [uv installed](installation.md):

```sh
uv sync --frozen --extra desktop --python 3.12
uv run --frozen --extra desktop tingsub gui
```

Or double-click `gui.command`. If models have not been downloaded, open **Local models**, read the license notice and choose **Prepare models**. Preparation needs an internet connection. Existing complete model snapshots are reused; the interface reports file presence, and the service validates/loads them during startup.

Choose **Start service** and wait for **Models are ready**. **Browser connection** explains extension installation and provides a button to copy your pairing code. Open a video and start captions from the Chrome extension; a desktop button cannot grant Chrome permission to capture a tab.

### Optional Finder / Dock launcher

```sh
uv run --frozen --extra desktop python scripts/create_desktop_app.py
open .local/TingSub.app
```

This creates a **local launcher**, not a self-contained or signed distribution. It depends on this checkout and its `.venv`; keep them in place. You can drag the app to the Dock. Recreate it after moving the checkout or rebuilding the environment. No login item or background daemon is installed.

## Controls and lifecycle

- **Captions:** spoken language, caption languages, live drafts and font size. Changes are shared with the paired extension and apply when the next caption session starts. Stop and restart captions to apply them.
- **Local models:** download/readiness state, actual weight file sizes and recent process output. Download and inference cannot run simultaneously from this window. Use Cancel to stop an owned preparation/startup.
- **Browser connection:** extension folder, pairing code and installation guide. Copying a pairing code puts it on the system clipboard; the desktop does not display it in its page or logs.
- **Settings:** interface language and appearance. These preferences do not change speech or caption languages.

Closing the window stops the service or download **started by that window**, including an active caption session. A compatible service already started in a terminal is shown as external; this window never stops it. A service using a different pairing code, an older service without shared preferences, or another program on port 18765 is shown as a conflict. Stop it in its original window first. Preparing models after a cancelled download reuses the model cache.

Settings live in `.local/preferences.json` (captions) and `.local/interface.json` (appearance); process output goes to `.local/desktop.log`, replaced at the next start/preparation. Errors can include local file paths, so review logs before sharing. To use a custom data directory, place the global option before `gui`: `tingsub --data-dir PATH gui`. It must match the service's pairing and model directory.

With a pairing code configured, the extension durably retains edits while the service is unavailable. Before starting captions it retries those writes, then reads shared preferences. If retry fails, capture does not start with stale settings. Once synchronized, later desktop or extension edits take precedence. Old services without `/preferences` retain extension-only behavior. Reload the unpacked extension after updating this checkout.

## Current scope

Apple Silicon macOS only. No standalone DMG, auto-update, tray mode or automatic tab capture. The existing terminal workflow remains supported. The extension UI and some process/error messages remain Chinese even when the desktop interface is English. See [development](development.md) for separate browser and native WebKit checks.

Desktop operations use a cross-process lock per data directory, preventing multiple windows from preparing models or overwriting logs/configuration concurrently. The child inherits the lock so an unexpected desktop exit does not permit a competing job.

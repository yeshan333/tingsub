[English](../en/privacy.md) · [简体中文](../zh-CN/privacy.md) · [Index](README.md)

# Privacy and permissions

## Data flow

TingSub sends audio from the tab you explicitly start to `127.0.0.1:18765` on the same machine. Recognition and translation run in the local Python process. There is no cloud API, telemetry, account system or cloud fallback in this implementation. Dependency installation and `prepare` contact package registries/Hugging Face; the video website's own traffic is outside TingSub.

Normal caption sessions keep audio segments and text in memory; they do not automatically write recordings or transcript files. The overlay shows up to two recent segments and clears stale text. This is not a guarantee of secure memory erasure. The operating system, browser, video website and other software have their own behavior.

Developer benchmark scripts intentionally write generated audio, transcripts, timings and screenshots under ignored `.local/`. They print inference results to the terminal. Review these files before sharing diagnostics. Routine server access logging is disabled, but error messages can still contain local details.

## Browser permissions

| Permission | Why it exists |
| --- | --- |
| `activeTab` | Access the page after the user's toolbar action |
| `tabCapture` | Capture selected-tab audio, not microphone input |
| `offscreen` | Keep the audio pipeline alive after closing the popup |
| `scripting` | Insert the caption overlay into the selected page |
| `storage` | Save settings and pairing code locally, without browser sync |
| `http://127.0.0.1/*` | Reach the local service; Chrome host permissions are host-scoped, while connection code/CSP target port 18765 |

No all-sites host access or microphone permission is requested. Page navigation stops capture. Captions live in the page's DOM (an open shadow root): the active website can inspect displayed text. Do not treat an in-page overlay as confidential from that website. The pairing code stays in extension storage and is not injected into page DOM.

## Local secrets

`.local/token` is created with owner-only file permissions and is shared with the extension for WebSocket authentication. Protect it like a password. The extension-origin check is an additional browser boundary, not a substitute for the token. Software already running under your local account is outside this boundary.

To rotate: stop the service and captions, remove only `.local/token`, run `uv run --frozen tingsub pair` to create a new code, replace it in the extension and restart the service. Do not remove the entire data directory just to rotate a token. See [uninstall instructions](installation.md) for removal and [security policy](../../SECURITY.md) for reporting issues.

## Desktop local data

The desktop adds no audio upload or telemetry. Caption preferences live in `.local/preferences.json`, appearance in `.local/interface.json`. Subprocess output goes to `.local/desktop.log`, replaced on each start/preparation; it does not intentionally record audio or transcripts, but errors can contain local paths. The pairing code reaches the system clipboard only on Copy and is not intentionally displayed in the page or logs. Installing desktop dependencies contacts package registries; model preparation and documentation links require explicit user actions.

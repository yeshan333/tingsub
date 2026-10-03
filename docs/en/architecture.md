[English](../en/architecture.md) · [简体中文](../zh-CN/architecture.md) · [Index](README.md)

# Architecture and protocol

## Components

| File | Responsibility |
| --- | --- |
| `extension/background.js` | User gesture, active-tab access, offscreen lifecycle, message routing |
| `extension/offscreen.js` | Capture, audio playback, WebSocket ownership and shutdown |
| `extension/pcm-worklet.js` | Mono PCM16 framing and capture timestamps |
| `extension/overlay.js` | Shadow DOM captions, stale-result suppression, fullscreen and controls |
| `src/live_subs/audio.py` | VAD segmentation and bounded pending work |
| `src/live_subs/server.py` | Loopback service, pairing and single-session ownership |
| `src/live_subs/pipeline.py` | Scheduling, early Chinese events, errors and metrics |
| `src/live_subs/engine.py` | Local MLX recognition, translation, quality checks and prompt cache |
| `src/live_subs/cli.py` | Model preparation, pairing and service startup |

## Audio and scheduling

Chrome captures only the selected tab. A native-rate audio path restores audible playback; an AudioContext performs sample-rate conversion to 16 kHz. The worklet averages channels and emits 20 ms / 320-sample PCM16 frames. Missing channels emit silence while the clock advances.

The server applies an RMS gate and WebRTC VAD, keeps 200 ms of pre-roll, and submits after approximately 240 ms of VAD silence or a 3-second maximum segment. VAD hangover adds time beyond the configured silence interval. Optional drafts are considered every 800 ms. A short tail after a forced split is retained, while an independent very short noise burst is filtered. A capture timestamp discontinuity closes the old segment instead of joining unrelated audio.

One dedicated inference thread owns MLX execution. Pending work is bounded to three final segments plus the latest draft; final work takes priority. Waiting/capture age over 2.5 seconds causes explicit skipping before inference. Already-running GPU work is not forcibly interrupted. Navigation/disconnection can therefore leave a short period of in-flight work.

Whisper uses one encoded feature set for language detection and transcription. Repetition and low-confidence output are rejected. Translation is final-only: English source text is reused as English; Japanese bilingual output is generated with Chinese first. A complete JSON Chinese string is emitted immediately, then the final result. Prompt caches retain only verified common token prefixes; no conversation history is intentionally added. Captions use `textContent`, not model-generated HTML.

## Local protocol (version 1)

This is an internal protocol, not a stable third-party API. Identifiers containing `tingqiao` remain for compatibility with the original prototype.

- `GET /health`: readiness, busy flag, `service: "tingqiao"`, `protocol: 1`; no authentication and no transcript data.
- `WS /stream`: extension-origin check, followed by a pairing-token handshake within 5 seconds. The origin check alone is not authentication. One authenticated stream at a time.
- Initial JSON: `{"token":"<local pairing code>","language":"en","display":"zh-en","partials":true}`. Languages: `en`, `ja`, `auto`; displays: `zh-en`, `source-zh`.
- After `ready`, send binary packets: little-endian float64 packet-end Unix time in milliseconds (8 bytes), followed by 320 little-endian signed int16 samples (640 bytes), total 648 bytes.
- `{"type":"ping"}` returns `pong`. `{"type":"stop"}` drains the final segment and pending work, then sends `done`. Disconnect cancels waiting work rather than guaranteeing a drain.
- Server events: `ready`, `transcript`, `translation_progress`, `translation`, `rejected`, `dropped`, `notice`, `error`, `pong`, `done`.

Caption events share a segment `id`. `transcript` has `source`, `language`, `final`, display and timing fields. `translation_progress` adds `zh`; `translation` adds the final `zh`, `en`, inference timings and metrics. Rejections have `reason`, while failures include a human-readable `message`. Consumers must ignore older drafts after a final/translated result, and results for expired history. Only the newest two segments are displayed; silent captions are cleared after 15 seconds.

Metrics contain session counters and rolling P50/P95 values over up to 256 successfully translated segments. See [metric definitions](benchmarks.md). The extension and service must be upgraded together for protocol changes.

## Boundaries

The service binds loopback only. No cloud fallback or model downloads occur during serving. There is no microphone mode, transcript export, multi-user API, persistent transcript database, speaker diarization or sentence-level accuracy guarantee. GPU backends other than Apple MLX require separate implementation and validation.

## Desktop control and shared settings

The optional `desktop` extra uses macOS WebKit through pywebview. All page assets ship in the package. A limited bridge starts/stops owned subprocesses, prepares models, copies the pairing code and opens fixed resources. There are no remote fonts or scripts. CSP permits `unsafe-eval` because pywebview 6 dynamically constructs bridge methods; inline scripts remain blocked and resources/connections stay same-origin.

`GET /preferences` and `PATCH /preferences` require `Authorization: Bearer <pairing code>`. When Origin is present, only Chrome extension origins are accepted. The schema allows language, display mode, drafts and integer font sizes 18–40; a file lock and atomic replacement preserve independent desktop/extension edits. There are no HTTP administration endpoints for start, stop or model downloads. The extension reads shared preferences before capture; existing WebSocket session parameters do not change.

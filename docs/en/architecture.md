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

Caption events share a segment `id`. `transcript` has `source`, `language`, `final`, display and timing fields. `translation_progress` adds `zh`; `translation` adds the final `zh`, `en`, inference timings and metrics. Rejections have `reason`, while failures include a human-readable `message`. Consumers must ignore older drafts after a final/translated result, and results for expired history. The overlay retains at most two segments, displaying one translation and the next recognition draft; silent captions are cleared after 15 seconds.

Metrics contain session counters and rolling P50/P95 values over up to 256 successfully translated segments. See [metric definitions](benchmarks.md). The extension and service must be upgraded together for protocol changes.

## Boundaries

The service binds loopback only. No cloud fallback or model downloads occur during serving. There is no microphone mode, transcript export, multi-user API, persistent transcript database, speaker diarization or sentence-level accuracy guarantee. GPU backends other than Apple MLX require separate implementation and validation.

## Desktop control and shared settings

The desktop host uses [MyGo](https://github.com/egoist/mygo), pinned in `go.mod`/`go.sum`, with macOS WKWebView. Go embeds the existing HTML/CSS/JavaScript assets and owns the window, menu bar and application lifecycle. The page calls an explicit `Desktop` Go service through `window.mygo.call`; there are no remote fonts or scripts, inline scripts, or `unsafe-eval`. Python retains MLX inference, model preparation, preferences, pairing and the existing browser protocol.

`GET /preferences` and `PATCH /preferences` require `Authorization: Bearer <pairing code>`. When Origin is present, only Chrome extension origins are accepted. The schema allows language, display mode, drafts and integer font sizes 18–40; a file lock and atomic replacement preserve independent desktop/extension edits. There are no HTTP administration endpoints for start, stop or model downloads. The extension reads shared preferences before capture; existing WebSocket session parameters do not change.

The native navigation guard accepts only `mygo://localhost/` and its fragments. New windows and page permission requests are denied; CSP blocks child frames, and MyGo rejects bridge calls from subframes or untrusted origins. Go exposes only nine desktop methods, with no arbitrary dispatcher or lifecycle method. The Python controller runs as a private child over newline-delimited JSON on stdin/stdout, with a separate exact method allowlist; it adds no HTTP administration listener. Requests are serialized and bounded, errors redact the pairing code, and a canceled in-flight request closes the connection to avoid misrouting a later reply. Closing the window hides it; quitting closes the pipe and waits for cleanup. EOF after a host crash also stops owned work. An unresponsive controller and its owned process group are terminated after the shutdown deadline; external services are never adopted.

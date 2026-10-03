[English](../en/troubleshooting.md) · [简体中文](../zh-CN/troubleshooting.md) · [TingSub](../../README.md)

# Troubleshooting

| Symptom | Check or fix |
| --- | --- |
| Service unavailable / 本机服务未就绪 | Run `uv run --frozen tingsub serve` from the repository root. Wait for model warm-up. Check `curl http://127.0.0.1:18765/health`; a ready service reports `service: tingqiao`, `protocol: 1`. `tingqiao` is the retained internal protocol identifier. |
| Pairing rejected / 配对码错误 | Run `uv run --frozen tingsub pair` from the same data directory as the server; replace the popup code, then restart capture. Do not post this code in issues. |
| Port occupied | Check `lsof -nP -iTCP:18765 -sTCP:LISTEN`. If it is another TingSub instance, use or stop that instance. Do not kill an unknown process. Changing the server port alone does not change the extension. |
| Models missing / download fails | Run `uv run --frozen tingsub prepare` with network access. Verify the snapshot paths in `.local/models.json`. Retry interrupted downloads; use `--force` only when intentionally refreshing or repairing models. Serving does not download missing files. |
| Another connection is active | Stop the other tab or benchmark. Only one connection owns inference. After an unexpected browser exit, allow the socket to disconnect; restart the service if it remains busy. |
| No sound or no captions | Confirm the selected tab is playing audible speech and is not muted. Click the extension toolbar action again. Start on a normal web page, not `chrome://` or an extension page. Check whether the popup receives audio. Music alone may be rejected as non-speech or low-confidence speech. |
| Captions stop after navigation | This is expected. Wait for the new page, then start a new session. |
| Extension updated but old overlay remains | Reload TingSub in `chrome://extensions`, refresh the video page, and start again. |
| Caption lag / dropped segments | Select the known input language, disable drafts, stop other GPU workloads, and restart capture. A 3-second segment still requires audio collection before final output. Read first-text and first-Chinese latency as well as tail latency. |
| Wrong words or empty captions | Background music, overlapping voices, proper names and forced boundaries are known limitations. Check rejection counters. Switching to a fixed input language can help language selection, but does not guarantee accuracy. |
| macOS voices missing in real-model tests | Install the Samantha and Kyoko voices in macOS speech settings; `say -v '?'` lists available voices. These fixtures are test-only. |
| `npm ci` fails after editing dependencies | Regenerate `package-lock.json` with `npm install`, review it, then rerun `npm ci`. Users do not need npm to run the extension. |

If unresolved, open a [bug report](https://github.com/yeshan333/tingsub/issues/new?template=bug_report.yml) in English or Chinese. Include macOS/Chrome versions, chip/RAM, commit, settings, observed counters and minimal reproduction. Redact pairing codes, usernames, private paths, audio and transcripts. See [security reporting](../../SECURITY.md) for vulnerabilities.

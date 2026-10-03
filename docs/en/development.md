[English](../en/development.md) · [简体中文](../zh-CN/development.md) · [Index](README.md)

# Development

## Reproduce the checkout

Use Python 3.12 via uv, Node.js 22+, and macOS on Apple Silicon for the complete development environment. Dependencies are locked in `uv.lock` and `package-lock.json`.

```sh
uv sync --frozen --python 3.12
npm ci
uv run --frozen ruff check src tests scripts
uv run --frozen pytest -v
python3 scripts/check_docs.py
npm run check
npm test
npx playwright install chromium
npm run test:browser
npm run test:desktop
```

These checks do not download model weights and do not need a running inference service. Python tests use explicit fake engines to check contracts; browser rendering tests inject protocol fixtures. Neither measures ASR accuracy. Playwright creates an isolated profile and does not change your daily Chrome profile. Screenshots stay in ignored `.local/`.

## Real inference

Follow [installation](installation.md), prepare models and start the service. Stop any existing caption session before benchmarks. See [benchmarks](benchmarks.md) for the separate model and capture commands. Direct model checks must run with the service stopped to avoid competing GPU processes.

## CI

GitHub Actions runs Python lint/unit tests and package build on macOS ARM64, and JavaScript/isolated Chromium plus documentation checks on Linux. Workflow permissions are read-only, actions are pinned to commit hashes, dependency locks are committed, and model weights are not downloaded. The uploaded extension archive contains only extension source. A green CI result means the logic, packaging and renderer checks passed; it does not certify Metal inference or live-stream accuracy.

## Making changes

1. Fork and create a focused branch from `main`.
2. Make the change and add meaningful regression coverage when behavior changes.
3. Run relevant checks above; for protocol changes check both server and extension.
4. Update matching English/Chinese pages, plus both changelogs for user-visible changes.
5. Open a PR explaining the trigger, new behavior and actual validation performed.

Do not commit `.local`, tokens, snapshots, private audio, transcripts or browser profiles. Do not add cloud fallback, telemetry or broader extension permissions without an explicit design discussion. Review [contribution](../../CONTRIBUTING.md) and [security](../../SECURITY.md) policies.

## Dependency updates

Use `uv lock` for intentional Python changes and `npm install` for JavaScript changes, then review and commit both manifests and lockfiles. Run `uv sync --frozen` and `npm ci` after updating. Keep Python package and extension versions aligned. A model change also needs license review and real-model checks; `prepare` defaults are not a promise that any arbitrary checkpoint is compatible.

## Documentation i18n

`README.md` and root policy files are English; `.zh-CN.md` files are Simplified Chinese. Guides use matching filenames under `docs/en/` and `docs/zh-CN/`, with a language switch at the top. Both languages must carry the same commands, support matrix, caveats and license information. `scripts/check_docs.py` checks page pairing and repository-local link targets, not translation quality or remote URLs. Documentation i18n currently does not imply localized extension UI.

## Desktop validation

`npm run test:desktop` uses an explicit bridge fixture to check control calls, shared settings, external-service protection, both interface languages/themes and minimum window layout. It does not claim model inference. Screenshots are saved to `.local/desktop-*.png`.

For the native WebKit smoke check, install desktop dependencies, prepare models and stop any existing service:

```sh
uv run --frozen --extra desktop python scripts/check_desktop_native.py
```

This opens its own native window, clicks the real start/stop controls, waits for model warm-up, verifies the loopback API and checks that stopping releases the port. It cleans up its owned service and does not capture browser audio. CI does not download models to run this check.

The native check also verifies that navigation to a foreign URL is rejected. Add `--no-inference` to check the WebKit interface and navigation boundary without loading models.

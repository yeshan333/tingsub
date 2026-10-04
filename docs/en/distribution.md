[English](../en/distribution.md) · [简体中文](../zh-CN/distribution.md) · [Index](README.md)

# Standalone macOS distribution

End users open the DMG and drag TingSub to Applications. They do not install Python, uv, Homebrew or a source checkout. The first-run workflow downloads models and guides Chrome pairing. See [desktop setup](desktop.md). The app is about 1 GB before DMG compression; model caches are additional and are not bundled.

## Download a Release

Download the [macOS app (DMG)](https://github.com/yeshan333/tingsub/releases/latest/download/TingSub-macos-arm64.dmg) and [browser extension](https://github.com/yeshan333/tingsub/releases/latest/download/TingSub-extension.zip), or open [all Release assets and notes](https://github.com/yeshan333/tingsub/releases/latest). Public Release downloads need no GitHub login and are not subject to the 30-day Actions artifact retention period.

The app requires **Apple Silicon / macOS 15+** and includes its runtime: no Python, uv or Homebrew setup. Open the DMG and drag TingSub to Applications, or use the App ZIP. This is an early release **without Apple Developer ID signing or notarization**; macOS may show an unverified-developer prompt. Download models through the app on first use.

Extract the extension ZIP to a stable folder. In `chrome://extensions`, enable Developer mode and load the folder containing `manifest.json`. Alternatively, use **Open extension folder** in the app. Keep the same folder and reload on updates to preserve pairing. There is no Chrome Web Store listing yet.

Download all three archives and `SHA256SUMS` into one folder, then run `shasum -a 256 -c SHA256SUMS`. For individual downloads, run `shasum -a 256 <filename>` and compare the matching line in the manifest.

## Publish a version (maintainers)

1. Keep the versions in `pyproject.toml` and `extension/manifest.json` aligned, merge to main and wait for the complete CI run to pass.
2. Open [Publish Release](https://github.com/yeshan333/tingsub/actions/workflows/release.yml), select main and enter that successful CI run ID and matching `vX.Y.Z` tag.
3. The workflow checks provenance, versions and checksums, uploads the tested artifacts to a draft, verifies uploaded sizes and SHA-256 values, then publishes it. It never rebuilds binaries, replaces a published version or moves an existing tag. A failed upload can be retried for a draft targeting the same commit.

Each version uses the same asset names, so the homepage's `releases/latest/download/...` links follow the latest published version. Latest does not mean Apple-notarized or model-quality-certified. Routine CI continues to upload test artifacts without publishing every commit.

## Build

### Download a CI preview

Open [CI runs](https://github.com/yeshan333/tingsub/actions/workflows/ci.yml), select a successful **main** run, and scroll to **Artifacts**. GitHub requires signing in to download Actions artifacts; they are retained for **30 days**. These are preview builds, not GitHub Releases or Apple-notarized releases.

| Artifact | Contents |
| --- | --- |
| `TingSub-macos-arm64` | Versioned `.dmg`, `.app.zip`, and a SHA-256 file for each |
| `tingsub-extension` | `TingSub-extension-<version>.zip` and its SHA-256 file |

Extract GitHub's outer artifact ZIP first. For the app, open the DMG and drag TingSub to Applications, or extract the inner `.app.zip`. The minimum macOS version is in the filename; Apple Silicon is required. The app includes Python and the extension, but downloads model weights on first use. The desktop's **Open extension folder** button is the simplest way to install its matching browser extension.

To use the separate extension artifact, extract its inner ZIP into a **stable folder**, then in `chrome://extensions` enable Developer mode and load the folder containing `manifest.json`. Keep that folder when updating: replace its files and reload the existing extension, preserving Chrome's extension ID and pairing. The ZIP is not a CRX or a Chrome Web Store installer.

Verify the files from the extracted artifact directory:

```sh
shasum -a 256 -c *.sha256
```

Every PR, main push and manual CI run checks and packages the extension, then builds the macOS app after Python and browser checks pass. The reusable [Desktop bundle](https://github.com/yeshan333/tingsub/actions/workflows/desktop.yml) workflow can also be dispatched separately to rebuild only the app. No signing credentials, model downloads or Release publishing are required.

### Build locally

Maintainers need an Apple Silicon Mac and uv. The lockfile pins the build dependencies.

```sh
uv sync --frozen --extra desktop --group bundle --python 3.12
uv run --frozen --extra desktop --group bundle python scripts/build_desktop.py
```

Output: `.local/bundle/TingSub.app`, `TingSub-<version>-macos-<minimum>-arm64.dmg`, a matching `.app.zip`, and SHA-256 files. The app version comes from `pyproject.toml`; the extension package uses `extension/manifest.json`. Keep these versions aligned. PyInstaller includes the interpreter, native MLX libraries, Metal resources, inference dependencies, desktop assets and Chrome extension. Workers use the embedded executable, not PATH or a system Python. `--no-dmg` builds the App and App ZIP only.

Package the browser extension without macOS dependencies:

```sh
python3 scripts/package_extension.py
```

This writes a reproducible versioned ZIP and checksum to `dist/extension`, including only the explicit runtime file list and MIT license. If new extension resources are introduced, update the list in the packager too.

## Signing and notarization

With no signing configuration, PyInstaller uses ad-hoc signing. This supports local execution but is **not** Developer ID signing or Apple notarization. Downloaded artifacts may encounter Gatekeeper prompts. Do not disable system security or label these builds as notarized.

For a maintainer with installed Developer ID credentials, set `TINGSUB_CODESIGN_IDENTITY`. Optionally set `TINGSUB_NOTARY_PROFILE` to an existing `notarytool` keychain profile; the builder submits the DMG, waits for approval and staples the ticket. Keep credentials outside the repository. Verify a release on a clean Mac before publication. The current development build has not been notarized.

## Verify and maintain

CI checks both archive checksums, verifies DMG integrity, extracts the App ZIP into a temporary directory outside the checkout, verifies its signature, and starts the bundled CLI and native WebKit self-test with a minimal PATH and isolated data directory. That test uses `--no-inference`: it checks the packaged UI and navigation guard, not GPU inference or transcription quality. The packaged extension is separately extracted and loaded in real Chromium, including its popup and audio-capture resources. A missing archive or failed check fails CI instead of uploading an empty artifact.

```sh
/path/to/TingSub.app/Contents/MacOS/TingSub --self-test --data-dir /path/to/prepared-data
```

This opt-in check opens a real WebKit window, rejects foreign navigation, invokes the native bridge, starts a real model service and stops it. `--no-inference` only checks the native page and navigation policy. For standalone verification copy the App outside the checkout, run from `/tmp`, unset development environment variables and use a minimal system PATH. CLI diagnostics are available through `--worker --help`.

Data lives under `~/Library/Application Support/TingSub`. Updating the App preserves models, pairing and preferences. New installations export Chrome files to the stable `extensions/extension` path. Existing preview-version folders are also updated in place, so their Chrome IDs and local pairing/settings remain intact. After replacing the App, click **Open extension folder**, then **Reload** the existing extension in Chrome. Do not remove it or load a new copy. There is no automatic updater.

To uninstall, quit TingSub, remove it from Applications and remove its Chrome extension. Delete its Application Support directory only if you also want to delete cached models, pairing and settings. Source-based runs have a separate `.local` directory and are not migrated automatically.

Model weights retain upstream licenses and are downloaded separately. Third-party distribution metadata/license files are included under the App's resources; see [model and dependency notices](models.md). A successful build is not a licensing review or a quality benchmark.

The builder reads every bundled Mach-O dependency and sets `LSMinimumSystemVersion` to their highest minimum. The DMG filename includes this value. A build on a newer host can select newer MLX wheels and therefore cannot claim macOS 14 compatibility. Build and test on the oldest intended system to provide a compatible artifact; CI results alone are not inference validation.

"""Promote a successful main CI run to a public Release without rebuilding it."""

import argparse
import hashlib
import json
import os
import plistlib
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from zipfile import ZipFile

ASSETS = ("TingSub-macos-arm64.dmg", "TingSub-macos-arm64.app.zip", "TingSub-extension.zip")


def gh(*args: str) -> str:
    return subprocess.check_output(["gh", *args], text=True)


def api(repo: str, endpoint: str):
    return json.loads(gh("api", f"repos/{repo}/{endpoint}"))


def validate_run(run: dict, repo: str) -> str:
    if not (
        run["status"] == "completed"
        and run["conclusion"] == "success"
        and run["head_branch"] == "main"
        and run["event"] in {"push", "workflow_dispatch"}
        and run["path"] == ".github/workflows/ci.yml"
        and run["head_repository"]["full_name"] == repo
        and re.fullmatch(r"[0-9a-f]{40}", run["head_sha"])
    ):
        raise ValueError("Release requires a successful main CI run from this repository")
    return run["head_sha"]


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def prepare_assets(source: Path, output: Path, tag: str) -> str:
    if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", tag):
        raise ValueError("Expected a release tag such as v0.1.0")
    version = tag[1:]
    selected = []
    for pattern in (
        "TingSub-macos-arm64/*.dmg",
        "TingSub-macos-arm64/*.app.zip",
        "tingsub-extension/*.zip",
    ):
        matches = list(source.glob(pattern))
        if len(matches) != 1:
            raise ValueError(f"Expected exactly one artifact matching {pattern}")
        path = matches[0]
        checksum = Path(str(path) + ".sha256").read_text().split()
        if checksum != [digest(path), path.name]:
            raise ValueError(f"Checksum mismatch: {path.name}")
        selected.append(path)
    with ZipFile(selected[1]) as app:
        info = plistlib.loads(app.read("TingSub.app/Contents/Info.plist"))
    with ZipFile(selected[2]) as extension:
        manifest = json.loads(extension.read("manifest.json"))
    if info["CFBundleShortVersionString"] != version or manifest["version"] != version:
        raise ValueError("Release tag, app and extension versions must match")
    minimum = info["LSMinimumSystemVersion"]
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+){1,2}", minimum):
        raise ValueError("Invalid minimum macOS version")
    expected = f"TingSub-{version}-macos-{minimum}-arm64"
    if [p.name for p in selected] != [
        f"{expected}.dmg",
        f"{expected}.app.zip",
        f"TingSub-extension-{version}.zip",
    ]:
        raise ValueError("Artifact filenames do not match their version and platform")
    output.mkdir()
    for path, name in zip(selected, ASSETS, strict=True):
        shutil.copyfile(path, output / name)
    (output / "SHA256SUMS").write_text(
        "".join(f"{digest(output / name)}  {name}\n" for name in ASSETS)
    )
    return minimum


def release_notes(repo: str, tag: str, run_id: str, sha: str, minimum: str) -> str:
    return f"""## TingSub {tag}

### 简体中文

首个可直接下载的 TingSub 版本：本地语音识别、双语字幕、模型管理与 Chrome 扩展。

- **macOS 应用**：下载 `TingSub-macos-arm64.dmg`，拖入 Applications。
  Apple Silicon，macOS {minimum}+；无需安装 Python、uv 或 Homebrew。也提供 App ZIP。
- **浏览器插件**：下载 `TingSub-extension.zip`，解压到固定目录，
  在 `chrome://extensions` 开启开发者模式并加载。App 内也有配套插件入口。
- 首次使用在界面下载模型，然后配对浏览器；模型权重不在安装包内。
- **早期版本，尚未经过 Apple Developer ID 签名或公证**，
  macOS 可能提示无法验证开发者。不是 Chrome 商店版本。
- [安装说明](https://github.com/{repo}/blob/{sha}/docs/zh-CN/distribution.md) · [模型许可](https://github.com/{repo}/blob/{sha}/docs/zh-CN/models.md)

### English

Local transcription, bilingual captions, model management and a Chrome extension.

- Download the DMG and drag TingSub to Applications, or use the App ZIP. Requires Apple Silicon
  and macOS {minimum}+. No Python, uv or Homebrew installation needed.
- Extract the extension ZIP to a stable folder and load it in Chrome Developer mode. The app
  also includes the matching extension.
- Download models through the app on first use, then pair Chrome. Model weights are not bundled.
- **Early release, without Apple Developer ID signing or notarization.** macOS may show an
  unverified-developer prompt. No Chrome Web Store distribution yet.
- [Installation](https://github.com/{repo}/blob/{sha}/docs/en/distribution.md) · [Model licenses](https://github.com/{repo}/blob/{sha}/docs/en/models.md)

### Build / 构建

Commit: `{sha}` · [Verified CI run](https://github.com/{repo}/actions/runs/{run_id})

The extracted App and extension passed native WebKit / Chromium smoke checks. This does not
  measure model inference or subtitle quality.

Download `SHA256SUMS` beside the three archives and run `shasum -a 256 -c SHA256SUMS`.
"""


def publish(repo: str, run_id: str, tag: str) -> None:
    if not run_id.isdecimal() or not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", tag):
        raise ValueError("Expected a numeric CI run ID and a vX.Y.Z release tag")
    sha = validate_run(api(repo, f"actions/runs/{run_id}"), repo)
    # Never move an existing tag or replace a published version.
    refs = api(repo, f"git/matching-refs/tags/{tag}")
    if any(ref["ref"] == f"refs/tags/{tag}" for ref in refs):
        if api(repo, f"commits/{tag}")["sha"] != sha:
            raise ValueError("Existing release tag points to a different commit")
    releases = json.loads(gh("api", f"repos/{repo}/releases", "--paginate", "--slurp"))
    existing = next((r for page in releases for r in page if r["tag_name"] == tag), None)
    if existing and (not existing["draft"] or existing["target_commitish"] != sha):
        raise ValueError("Refusing to replace a published release or a different draft")
    with tempfile.TemporaryDirectory(prefix="tingsub-release-") as temporary:
        root = Path(temporary)
        source, output = root / "artifacts", root / "release"
        gh(
            "run",
            "download",
            run_id,
            "--repo",
            repo,
            "--name",
            "TingSub-macos-arm64",
            "--name",
            "tingsub-extension",
            "--dir",
            str(source),
        )
        minimum = prepare_assets(source, output, tag)
        notes = root / "notes.md"
        notes.write_text(release_notes(repo, tag, run_id, sha, minimum))
        if not existing:
            gh(
                "release",
                "create",
                tag,
                "--repo",
                repo,
                "--target",
                sha,
                "--draft",
                "--title",
                f"TingSub {tag}",
                "--notes-file",
                str(notes),
            )
        else:
            gh("release", "edit", tag, "--repo", repo, "--notes-file", str(notes))
        paths = [output / name for name in (*ASSETS, "SHA256SUMS")]
        gh("release", "upload", tag, "--repo", repo, "--clobber", *map(str, paths))
        # Verify uploaded bytes before making the draft publicly downloadable.
        release = json.loads(gh("release", "view", tag, "--repo", repo, "--json", "apiUrl"))
        remote = json.loads(gh("api", f"{release['apiUrl']}/assets"))
        if {item["name"] for item in remote} != {p.name for p in paths}:
            raise ValueError("Unexpected or missing Release assets; draft left unpublished")
        for path in paths:
            asset = next(item for item in remote if item["name"] == path.name)
            if (
                asset["size"] != path.stat().st_size
                or asset.get("digest") != f"sha256:{digest(path)}"
            ):
                raise ValueError(f"Uploaded asset verification failed: {path.name}")
        gh("release", "edit", tag, "--repo", repo, "--draft=false", "--latest")
        print(f"Published https://github.com/{repo}/releases/tag/{tag}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", "yeshan333/tingsub"))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()
    publish(args.repo, args.run_id, args.tag)

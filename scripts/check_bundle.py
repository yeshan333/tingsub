"""Verify the distributable archives and run the extracted native app without models."""

import argparse
import hashlib
import json
import os
import plistlib
import subprocess
import tempfile
from pathlib import Path


def verify(directory: Path):
    archives = sorted(directory.glob("*.app.zip"))
    disks = sorted(directory.glob("*.dmg"))
    if len(archives) != 1 or len(disks) != 1:
        raise ValueError("Expected exactly one App ZIP and one DMG in the build directory")
    for path in archives + disks:
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        expected = path.with_suffix(path.suffix + ".sha256").read_text().strip()
        if expected != f"{digest}  {path.name}":
            raise ValueError(f"Checksum mismatch: {path.name}")
    subprocess.run(["/usr/bin/hdiutil", "verify", str(disks[0])], check=True, timeout=120)
    with tempfile.TemporaryDirectory(prefix="tingsub-bundle-") as temp:
        root = Path(temp)
        subprocess.run(
            ["/usr/bin/ditto", "-x", "-k", str(archives[0]), str(root)], check=True, timeout=120
        )
        app = root / "TingSub.app"
        info = plistlib.loads((app / "Contents/Info.plist").read_bytes())
        subprocess.run(
            ["/usr/bin/codesign", "--verify", "--deep", "--strict", str(app)],
            check=True,
            timeout=60,
        )
        resources = app / "Contents/Resources"
        manifest = json.loads((resources / "extension/manifest.json").read_text())
        if manifest["version"] != info["CFBundleShortVersionString"]:
            raise ValueError("App and bundled extension versions differ")
        executable = app / "Contents/MacOS/TingSub"
        env = {"HOME": str(root), "PATH": "/usr/bin:/bin", "TMPDIR": temp, "LANG": "en_US.UTF-8"}
        subprocess.run(
            [str(executable), "--worker", "--help"],
            cwd=root,
            env=env,
            check=True,
            timeout=60,
        )
        # This runs on the CI Mac, without model downloads or inference. It proves
        # that the packaged WebKit UI and native bridge load outside the checkout.
        subprocess.run(
            [str(executable), "--self-test", "--no-inference", "--data-dir", str(root / "data")],
            cwd=root,
            env=env,
            check=True,
            timeout=90,
        )
        summary = (
            "## macOS distribution\n\n"
            f"- Version: `{info['CFBundleShortVersionString']}`\n"
            f"- Minimum macOS: `{info['LSMinimumSystemVersion']}`; Apple Silicon only\n"
            "- Verified: SHA-256, DMG integrity, extracted App signature, CLI, native WebKit UI\n"
            "- CI uses ad-hoc signing; no Developer ID or Apple notarization\n"
            "- Models are not bundled. No inference or transcription quality test was run.\n"
        )
        print(summary)
        if path := os.environ.get("GITHUB_STEP_SUMMARY"):
            with Path(path).open("a") as stream:
                stream.write(summary)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    verify(parser.parse_args().directory.resolve())

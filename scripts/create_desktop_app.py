"""Create a small local .app launcher backed by this checkout and its uv environment."""

import plistlib
import shlex
import shutil
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    app = ROOT / ".local" / "TingSub.app"
    contents = app / "Contents"
    binary = contents / "MacOS" / "TingSub"
    binary.parent.mkdir(parents=True, exist_ok=True)
    resources = contents / "Resources"
    resources.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "assets/brand/TingSub.icns", resources / "TingSub.icns")
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    info = {
        "CFBundleName": "TingSub",
        "CFBundleDisplayName": "TingSub",
        "CFBundleIdentifier": "io.github.yeshan333.tingsub",
        "CFBundleVersion": version,
        "CFBundleShortVersionString": version,
        "CFBundlePackageType": "APPL",
        "CFBundleExecutable": "TingSub",
        "CFBundleIconFile": "TingSub.icns",
        "NSHighResolutionCapable": True,
    }
    (contents / "Info.plist").write_bytes(plistlib.dumps(info))
    command = [sys.executable, "-m", "live_subs.cli", "--data-dir", str(ROOT / ".local"), "gui"]
    binary.write_text("#!/bin/sh\nexec " + shlex.join(command) + "\n")
    binary.chmod(0o755)
    print(app)


if __name__ == "__main__":
    main()

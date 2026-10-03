"""Create a small local .app launcher backed by this checkout and its uv environment."""

import plistlib
import shlex
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    app = ROOT / ".local" / "TingSub.app"
    contents = app / "Contents"
    binary = contents / "MacOS" / "TingSub"
    binary.parent.mkdir(parents=True, exist_ok=True)
    info = {
        "CFBundleName": "TingSub",
        "CFBundleDisplayName": "TingSub",
        "CFBundleIdentifier": "io.github.yeshan333.tingsub",
        "CFBundleVersion": "0.1.0",
        "CFBundleShortVersionString": "0.1.0",
        "CFBundlePackageType": "APPL",
        "CFBundleExecutable": "TingSub",
        "NSHighResolutionCapable": True,
    }
    (contents / "Info.plist").write_bytes(plistlib.dumps(info))
    command = [sys.executable, "-m", "live_subs.cli", "--data-dir", str(ROOT / ".local"), "gui"]
    binary.write_text("#!/bin/sh\nexec " + shlex.join(command) + "\n")
    binary.chmod(0o755)
    print(app)


if __name__ == "__main__":
    main()

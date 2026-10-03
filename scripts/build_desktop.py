"""Build the standalone Apple Silicon app and DMG using the locked bundle environment."""

import argparse
import hashlib
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-dmg", action="store_true")
    args = parser.parse_args()
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise SystemExit("Build on an Apple Silicon Mac")
    output = ROOT / ".local" / "bundle"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            str(ROOT / "packaging/TingSub.spec"),
            "--distpath",
            str(output),
            "--workpath",
            str(ROOT / ".local/pyinstaller"),
        ],
        check=True,
        cwd=ROOT,
    )
    app = output / "TingSub.app"
    subprocess.run(["/usr/bin/codesign", "--verify", "--deep", "--strict", str(app)], check=True)
    subprocess.run(
        [str(app / "Contents/MacOS/TingSub"), "--worker", "--help"],
        check=True,
        cwd="/tmp",
        env={"HOME": str(Path.home()), "PATH": "/usr/bin:/bin"},
    )
    if args.no_dmg:
        return
    staging = output / "dmg-staging"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir()
    subprocess.run(["/usr/bin/ditto", str(app), str(staging / "TingSub.app")], check=True)
    (staging / "Applications").symlink_to("/Applications")
    disk = output / "TingSub-0.1.0-macos-arm64.dmg"
    subprocess.run(
        [
            "/usr/bin/hdiutil",
            "create",
            "-volname",
            "TingSub",
            "-srcfolder",
            str(staging),
            "-ov",
            "-format",
            "UDZO",
            str(disk),
        ],
        check=True,
    )
    if identity := os.environ.get("TINGSUB_CODESIGN_IDENTITY"):
        subprocess.run(["/usr/bin/codesign", "--sign", identity, str(disk)], check=True)
    if profile := os.environ.get("TINGSUB_NOTARY_PROFILE"):
        if not os.environ.get("TINGSUB_CODESIGN_IDENTITY"):
            raise SystemExit("Notarization requires TINGSUB_CODESIGN_IDENTITY")
        subprocess.run(
            [
                "/usr/bin/xcrun",
                "notarytool",
                "submit",
                str(disk),
                "--keychain-profile",
                profile,
                "--wait",
            ],
            check=True,
        )
        subprocess.run(["/usr/bin/xcrun", "stapler", "staple", str(disk)], check=True)
    with disk.open("rb") as stream:
        checksum = hashlib.file_digest(stream, "sha256").hexdigest()
    disk.with_suffix(".dmg.sha256").write_text(f"{checksum}  {disk.name}\n")
    shutil.rmtree(staging)
    print(disk)


if __name__ == "__main__":
    main()

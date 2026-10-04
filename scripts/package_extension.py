"""Package only the browser extension's runtime files, plus its code license."""

import argparse
import hashlib
import json
import re
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    "manifest.json",
    "background.js",
    "offscreen.html",
    "offscreen.js",
    "pcm-worklet.js",
    "overlay.js",
    "popup.html",
    "popup.js",
    "popup.css",
)


def package(source: Path, license_file: Path, output: Path) -> Path:
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    version = manifest["version"]
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+){0,3}", version):
        raise ValueError("Expected a numeric Chrome extension version")
    # Read every required file first; a missing file must not leave a partial ZIP.
    files = {name: (source / name).read_bytes() for name in FILES}
    files["LICENSE"] = license_file.read_bytes()
    output.mkdir(parents=True, exist_ok=True)
    archive = output / f"TingSub-extension-{version}.zip"
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as bundle:
        for name, content in sorted(files.items()):
            entry = ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            entry.compress_type = ZIP_DEFLATED
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            bundle.writestr(entry, content)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(".zip.sha256").write_text(f"{digest}  {archive.name}\n")
    print(archive)
    return archive


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist/extension")
    args = parser.parse_args()
    package(ROOT / "extension", ROOT / "LICENSE", args.output)

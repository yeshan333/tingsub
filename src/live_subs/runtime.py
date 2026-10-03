"""Paths and worker commands shared by source and standalone builds."""

import hashlib
import shutil
import sys
from pathlib import Path


def bundled():
    return bool(getattr(sys, "frozen", False))


def default_data_directory():
    if bundled():
        return Path.home() / "Library" / "Application Support" / "TingSub"
    return Path(".local")


def extension_directory():
    if bundled():
        return Path(sys._MEIPASS) / "extension"
    return Path(__file__).resolve().parents[2] / "extension"


def worker_command(directory, command, *arguments):
    prefix = [sys.executable, "--worker"] if bundled() else [sys.executable, "-m", "live_subs.cli"]
    return [*prefix, "--data-dir", str(directory), command, *arguments]


def install_extension(directory):
    """Export a stable, content-versioned copy so Chrome survives app replacement."""
    source = extension_directory()
    if not (source / "manifest.json").is_file():
        raise RuntimeError("Bundled extension is missing")
    if not bundled():
        return source
    digest = hashlib.sha256()
    files = sorted(path for path in source.rglob("*") if path.is_file())
    for path in files:
        digest.update(str(path.relative_to(source)).encode())
        digest.update(path.read_bytes())
    target = directory / "extensions" / digest.hexdigest()[:16] / "extension"
    target.mkdir(parents=True, exist_ok=True)
    for path in files:
        destination = target / path.relative_to(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
    return target

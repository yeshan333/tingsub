"""Paths and worker commands shared by source and standalone builds."""

import re
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
    """Refresh the same unpacked path so Chrome retains its ID and local storage."""
    source = extension_directory()
    if not (source / "manifest.json").is_file():
        raise RuntimeError("Bundled extension is missing")
    if not bundled():
        return source
    exports = directory / "extensions"
    # Older previews exported content-addressed folders. Refresh those in place
    # too: Chrome's path-derived ID and its paired storage must survive updates.
    legacy = sorted(
        path / "extension" for path in exports.glob("*")
        if re.fullmatch(r"[0-9a-f]{16}", path.name)
        and (path / "extension" / "manifest.json").is_file()
    )
    stable = exports / "extension"
    target = stable if stable.exists() or not legacy else legacy[0]
    for destination in dict.fromkeys([target, *legacy]):
        shutil.copytree(source, destination, dirs_exist_ok=True)
    return target

"""Shared, validated caption preferences; no credentials are stored here."""

import fcntl
import json
import os
import tempfile
from pathlib import Path

DEFAULTS = {"language": "en", "display": "zh-en", "partials": True, "fontSize": 26}


def validate(patch):
    if not isinstance(patch, dict) or patch.keys() - DEFAULTS.keys():
        raise ValueError("Unknown caption preference")
    for key, value in patch.items():
        valid = {
            "language": lambda value=value: value in ("en", "ja", "auto"),
            "display": lambda value=value: value in ("zh-en", "source-zh"),
            "partials": lambda value=value: type(value) is bool,
            "fontSize": lambda value=value: type(value) is int and 18 <= value <= 40,
        }[key]()
        if not valid:
            raise ValueError(f"Invalid caption preference: {key}")
    return patch


def read_preferences(directory: Path):
    path = directory / "preferences.json"
    if not path.exists():
        return DEFAULTS.copy()
    return DEFAULTS | validate(json.loads(path.read_text()))


def update_preferences(directory: Path, patch):
    validate(patch)
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "preferences.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        result = read_preferences(directory) | patch
        fd, name = tempfile.mkstemp(dir=directory, prefix="preferences-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as output:
                json.dump(result, output)
            os.replace(name, directory / "preferences.json")
        finally:
            Path(name).unlink(missing_ok=True)
    return result

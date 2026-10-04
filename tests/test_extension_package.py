import hashlib
import importlib.util
import json
from pathlib import Path
from zipfile import ZipFile

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "package_extension", ROOT / "scripts/package_extension.py"
)
packager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packager)


def test_extension_archive_excludes_local_files_and_has_valid_checksum(tmp_path):
    source = tmp_path / "extension"
    source.mkdir()
    for name in packager.FILES:
        (source / name).write_bytes((ROOT / "extension" / name).read_bytes())
    (source / ".DS_Store").write_text("local metadata")
    (source / "token").write_text("not extension code")
    output = tmp_path / "dist"
    archive = packager.package(source, ROOT / "LICENSE", output)
    with ZipFile(archive) as bundle:
        assert set(bundle.namelist()) == set(packager.FILES) | {"LICENSE"}
        assert ".DS_Store" not in bundle.namelist()
        assert "token" not in bundle.namelist()
        assert "manifest.json" in bundle.namelist()  # Load unpacked selects this directory.
        assert json.loads(bundle.read("manifest.json"))["version"] in archive.name
        assert bundle.testzip() is None
    before = archive.read_bytes()
    packager.package(source, ROOT / "LICENSE", output)
    assert archive.read_bytes() == before
    digest = hashlib.sha256(before).hexdigest()
    assert archive.with_suffix(".zip.sha256").read_text() == f"{digest}  {archive.name}\n"


def test_extension_packaging_fails_when_audio_worklet_is_missing(tmp_path):
    source = tmp_path / "extension"
    source.mkdir()
    for name in packager.FILES:
        if name != "pcm-worklet.js":
            (source / name).write_bytes((ROOT / "extension" / name).read_bytes())
    output = tmp_path / "dist"
    with pytest.raises(FileNotFoundError, match="pcm-worklet"):
        packager.package(source, ROOT / "LICENSE", output)
    assert not output.exists()

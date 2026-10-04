import hashlib
import importlib.util
import json
import plistlib
from pathlib import Path
from zipfile import ZipFile

import pytest

spec = importlib.util.spec_from_file_location(
    "publish_release", Path(__file__).resolve().parents[1] / "scripts/publish_release.py"
)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


def successful_run():
    return dict(
        status="completed",
        conclusion="success",
        head_branch="main",
        event="push",
        path=".github/workflows/ci.yml",
        head_sha="a" * 40,
        head_repository={"full_name": "owner/repo"},
    )


@pytest.mark.parametrize(
    "change",
    [
        {"conclusion": "failure"},
        {"status": "in_progress"},
        {"event": "pull_request"},
        {"head_branch": "feature"},
        {"path": ".github/workflows/desktop.yml"},
        {"head_repository": {"full_name": "fork/repo"}},
    ],
)
def test_release_rejects_failed_incomplete_pr_or_untrusted_builds(change):
    run = successful_run() | change
    with pytest.raises(ValueError, match="successful main CI"):
        release.validate_run(run, "owner/repo")


def test_successful_main_ci_release_uses_the_tested_commit():
    assert release.validate_run(successful_run(), "owner/repo") == "a" * 40


@pytest.fixture
def artifacts(tmp_path):
    source = tmp_path / "artifacts"
    desktop = source / "TingSub-macos-arm64"
    extension = source / "tingsub-extension"
    desktop.mkdir(parents=True)
    extension.mkdir()
    stem = "TingSub-0.1.0-macos-15.0-arm64"
    (desktop / f"{stem}.dmg").write_bytes(b"fixture dmg bytes, not an installation test")
    with ZipFile(desktop / f"{stem}.app.zip", "w") as app:
        app.writestr(
            "TingSub.app/Contents/Info.plist",
            plistlib.dumps(
                {
                    "CFBundleShortVersionString": "0.1.0",
                    "LSMinimumSystemVersion": "15.0",
                }
            ),
        )
    with ZipFile(extension / "TingSub-extension-0.1.0.zip", "w") as archive:
        archive.writestr("manifest.json", json.dumps({"version": "0.1.0"}))
    for path in list(source.glob("*/*")):
        Path(str(path) + ".sha256").write_text(
            f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n"
        )
    return source


def test_release_preserves_ci_bytes_under_stable_download_names(artifacts, tmp_path):
    output = tmp_path / "release"
    assert release.prepare_assets(artifacts, output, "v0.1.0") == "15.0"
    assert {p.name for p in output.iterdir()} == {*release.ASSETS, "SHA256SUMS"}
    original = {p.read_bytes() for p in artifacts.glob("*/*") if not p.name.endswith(".sha256")}
    assert {p.read_bytes() for p in output.iterdir() if p.name != "SHA256SUMS"} == original
    for line in (output / "SHA256SUMS").read_text().splitlines():
        expected, name = line.split()
        assert hashlib.sha256((output / name).read_bytes()).hexdigest() == expected


@pytest.mark.parametrize("fault", ["corrupt", "missing", "version"])
def test_release_rejects_damaged_missing_or_mismatched_artifacts(artifacts, tmp_path, fault):
    if fault == "corrupt":
        next(artifacts.glob("*/*.dmg")).write_bytes(b"changed after CI")
    if fault == "missing":
        next(artifacts.glob("*/*.dmg")).unlink()
    output = tmp_path / "release"
    with pytest.raises(ValueError):
        release.prepare_assets(artifacts, output, "v0.2.0" if fault == "version" else "v0.1.0")
    assert not output.exists()


@pytest.mark.parametrize("requested,current", [("v1.1.0", "v1.2.0"), ("v1.9.0", "v1.10.0")])
def test_older_release_cannot_redirect_homepage_downloads(requested, current):
    with pytest.raises(ValueError, match="newer release"):
        release.validate_version_order(
            [{"tag_name": current, "draft": False, "prerelease": False}], requested
        )


def test_first_or_newer_release_can_become_latest_ignoring_future_drafts():
    release.validate_version_order([], "v0.1.0")
    release.validate_version_order(
        [
            {"tag_name": "v1.9.0", "draft": False, "prerelease": False},
            {"tag_name": "v2.0.0", "draft": True, "prerelease": False},
            {"tag_name": "v3.0.0", "draft": False, "prerelease": True},
        ],
        "v1.10.0",
    )

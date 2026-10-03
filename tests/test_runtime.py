import sys

from live_subs.runtime import default_data_directory, install_extension, worker_command


def test_standalone_worker_reuses_embedded_executable_and_persistent_user_directory(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    directory = default_data_directory()
    assert directory.parts[-3:] == ("Library", "Application Support", "TingSub")
    assert worker_command(directory, "prepare", "--validate") == [
        sys.executable,
        "--worker",
        "--data-dir",
        str(directory),
        "prepare",
        "--validate",
    ]


def test_exported_extension_updates_at_the_same_path_so_chrome_keeps_its_identity(
    tmp_path,
    monkeypatch,
):
    bundle = tmp_path / "bundle"
    extension = bundle / "extension"
    extension.mkdir(parents=True)
    (extension / "manifest.json").write_text('{"version":"1"}')
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    data = tmp_path / "data"
    first = install_extension(data)
    assert first == install_extension(data)
    (extension / "manifest.json").write_text('{"version":"2"}')
    second = install_extension(data)
    assert first == second == data / "extensions" / "extension"
    assert (first / "manifest.json").read_text() == '{"version":"2"}'
    assert (second / "manifest.json").read_text() == '{"version":"2"}'


def test_updating_legacy_exports_keeps_each_existing_chrome_path_usable(tmp_path, monkeypatch):
    bundle = tmp_path / "bundle"
    source = bundle / "extension"
    source.mkdir(parents=True)
    (source / "manifest.json").write_text('{"version":"2"}')
    (source / "worker.js").write_text("updated worker")
    data = tmp_path / "data"
    old_paths = [data / "extensions" / digest / "extension" for digest in ("a" * 16, "b" * 16)]
    for path in old_paths:
        path.mkdir(parents=True)
        (path / "manifest.json").write_text('{"version":"1"}')
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    first = install_extension(data)
    assert first in old_paths
    for path in old_paths:
        assert (path / "manifest.json").read_text() == '{"version":"2"}'
        assert (path / "worker.js").read_text() == "updated worker"
    (source / "manifest.json").write_text('{"version":"3"}')
    assert install_extension(data) == first
    assert not (data / "extensions" / "extension").exists()

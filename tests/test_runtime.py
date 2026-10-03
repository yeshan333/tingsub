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


def test_exported_extension_survives_app_replacement_and_new_version_has_separate_folder(
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
    assert first != second
    assert (first / "manifest.json").read_text() == '{"version":"1"}'
    assert (second / "manifest.json").read_text() == '{"version":"2"}'

import sys
from pathlib import Path
from unittest.mock import Mock

from live_subs import desktop_launcher


def test_source_launcher_builds_from_checkout_and_passes_absolute_python_and_data_paths(
    tmp_path, monkeypatch,
):
    root = tmp_path / "checkout with spaces"
    root.mkdir()
    (root / "go.mod").touch()
    monkeypatch.setattr(desktop_launcher, "__file__", root / "src/live_subs/desktop_launcher.py")
    build = Mock()
    monkeypatch.setattr(desktop_launcher.subprocess, "run", build)
    data = tmp_path / "data with spaces"
    command = desktop_launcher.desktop_command(data, "--self-test", "--no-inference")
    assert command == [
        str(root / ".local/bin/TingSub"), "--python", sys.executable,
        "--source-root", str(root), "--data-dir", str(data), "--self-test", "--no-inference",
    ]
    assert build.call_args.kwargs == {"cwd": root, "check": True}
    assert build.call_args.args[0][-1] == "./cmd/tingsub"


def test_bundled_gui_launch_uses_sibling_mygo_host_without_requiring_go(tmp_path, monkeypatch):
    executable = tmp_path / "TingSub.app/Contents/MacOS/TingSub-worker"
    monkeypatch.setattr(sys, "executable", str(executable))
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    build = Mock(side_effect=AssertionError("A bundled app must not compile Go"))
    monkeypatch.setattr(desktop_launcher.subprocess, "run", build)
    assert desktop_launcher.desktop_command(Path("/data")) == [
        str(executable.with_name("TingSub")), "--data-dir", "/data",
    ]
    build.assert_not_called()

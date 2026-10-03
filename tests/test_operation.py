import os
import subprocess
import sys

import pytest

from live_subs.operation import acquire_operation


def test_inherited_worker_keeps_terminal_jobs_locked_after_parent_releases_its_handle(tmp_path):
    parent = acquire_operation(tmp_path)
    code = """
import sys
from pathlib import Path
from live_subs.operation import acquire_operation
with acquire_operation(Path(sys.argv[1]), sys.argv[2]):
    print('locked', flush=True)
    sys.stdin.readline()
"""
    child = subprocess.Popen([sys.executable, "-c", code, str(tmp_path), str(parent.fileno())],
                             pass_fds=(parent.fileno(),), stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, text=True)
    try:
        assert child.stdout.readline().strip() == "locked"
        parent.close()
        with pytest.raises(RuntimeError, match="window or terminal"):
            acquire_operation(tmp_path)
        child.communicate("exit\n", timeout=5)
        assert child.returncode == 0
        with acquire_operation(tmp_path):
            pass
    finally:
        parent.close()
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5)


def test_worker_cannot_reuse_an_unrelated_descriptor_as_the_operation_lock(tmp_path):
    with acquire_operation(tmp_path), (tmp_path / "other").open("w") as other:
        with pytest.raises(RuntimeError, match="does not match"):
            acquire_operation(tmp_path, other.fileno())


@pytest.mark.parametrize("command", ["prepare", "serve"])
def test_terminal_commands_cannot_start_while_desktop_holds_directory_lock(tmp_path, command):
    with acquire_operation(tmp_path):
        env = {k: v for k, v in os.environ.items() if k != "TINGSUB_OPERATION_FD"}
        child = subprocess.run([sys.executable, "-m", "live_subs.cli", "--data-dir",
                                str(tmp_path), command], env=env, capture_output=True, timeout=5)
    assert child.returncode != 0
    assert b"window or terminal" in child.stderr
    assert not (tmp_path / "models.json").exists()

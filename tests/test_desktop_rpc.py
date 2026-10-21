import io
import json
import os
import subprocess
import sys
from unittest.mock import Mock

import pytest

from live_subs.desktop import DesktopController
from live_subs.desktop_rpc import dispatch, methods_for, run


@pytest.mark.parametrize("name", [
    "close", "_controller._token.__str__", "__class__", "snapshot.__self__", "unknown",
])
def test_desktop_requests_cannot_call_lifecycle_or_private_methods(tmp_path, name):
    controller = DesktopController(tmp_path)
    with pytest.raises(ValueError, match="Unknown desktop method"):
        dispatch({"method": name, "params": []}, methods_for(controller))


@pytest.mark.parametrize("message", [None, [], {}, {"method": "snapshot", "params": {}},
                                      {"method": "snapshot", "params": [], "extra": True}])
def test_malformed_desktop_requests_are_rejected_before_dispatch(message):
    snapshot = Mock()
    with pytest.raises(ValueError):
        dispatch(message, {"snapshot": snapshot})
    snapshot.assert_not_called()


def test_host_pipe_eof_closes_owned_work_and_keeps_responses_valid_after_bad_request(tmp_path):
    controller = DesktopController(tmp_path)
    controller.close = Mock()
    output = io.StringIO()
    run(controller, io.StringIO('not-json\n{"method":"get_interface","params":[]}\n'), output)
    responses = [json.loads(line) for line in output.getvalue().splitlines()]
    assert "error" in responses[0]
    assert responses[1]["result"] == {"locale": "zh-CN", "theme": "dark"}
    controller.close.assert_called_once()


def test_oversized_host_request_closes_owned_work_without_dispatch(tmp_path):
    controller = DesktopController(tmp_path)
    controller.close = Mock()
    with pytest.raises(ValueError, match="too large"):
        run(controller, io.StringIO("x" * 65537), io.StringIO())
    controller.close.assert_called_once()


def test_failed_desktop_request_redacts_pairing_secret_from_error(tmp_path, monkeypatch):
    controller = DesktopController(tmp_path)
    monkeypatch.setattr(controller, "snapshot", Mock(side_effect=RuntimeError(controller._token)))
    output = io.StringIO()
    run(controller, io.StringIO('{"method":"snapshot","params":[]}\n'), output)
    assert controller._token not in output.getvalue()
    assert json.loads(output.getvalue())["error"] == "[redacted]"


def test_menu_service_action_rechecks_ownership_and_does_not_stop_an_external_service(tmp_path):
    controller = DesktopController(tmp_path)
    controller.service_status = Mock(return_value={"state": "ready", "owned": False})
    controller.start_service, controller.stop_service = Mock(), Mock()
    assert dispatch({"method": "service_action", "params": []}, methods_for(controller)) == {
        "ok": False,
    }
    controller.start_service.assert_not_called()
    controller.stop_service.assert_not_called()


def test_real_python_sidecar_persists_interface_and_exits_when_host_closes_pipe(tmp_path):
    process = subprocess.run(
        [sys.executable, "-m", "live_subs.cli", "--data-dir", str(tmp_path), "desktop-rpc"],
        input='{"method":"save_interface","params":[{"locale":"en","theme":"light"}]}\n'
              '{"method":"get_interface","params":[]}\n',
        capture_output=True, text=True, timeout=15,
    )
    assert process.returncode == 0, process.stderr
    responses = [json.loads(line) for line in process.stdout.splitlines()]
    assert responses[1]["result"] == {"locale": "en", "theme": "light"}
    assert json.loads((tmp_path / "interface.json").read_text()) == responses[1]["result"]


def test_host_disconnection_terminates_its_owned_child_and_releases_operation_lock(tmp_path):
    # Run the actual RPC EOF handler with a sleeping owned child, without models.
    program = '''
import io, subprocess, sys
from live_subs.desktop import DesktopController
from live_subs.desktop_rpc import run
c = DesktopController(sys.argv[1])
c._operation_lock = c._acquire_operation()
c._process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
print(c._process.pid, flush=True)
run(c, sys.stdin, io.StringIO())
'''
    process = subprocess.Popen(
        [sys.executable, "-c", program, str(tmp_path)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
    )
    try:
        child = int(process.stdout.readline())
        process.stdin.close()
        assert process.wait(timeout=15) == 0
        with pytest.raises(ProcessLookupError):
            os.kill(child, 0)
        controller = DesktopController(tmp_path)
        controller._acquire_operation().close()
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        process.stdout.close()

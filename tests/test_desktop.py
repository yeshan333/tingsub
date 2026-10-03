import json
import subprocess
import threading
from unittest.mock import Mock

import pytest

from live_subs.desktop import DesktopAPI, DesktopController
from live_subs.preferences import read_preferences, update_preferences


def models_at(directory):
    folder = directory / "model"
    folder.mkdir()
    (folder / "config.json").write_text("{}")
    (folder / "weights.safetensors").write_bytes(b"fixture, not inference weights")
    (directory / "models.json").write_text(
        json.dumps(
            {kind: {"path": str(folder), "repo": f"test/{kind}"} for kind in ("asr", "translation")}
        )
    )


@pytest.fixture
def controller(tmp_path, monkeypatch):
    monkeypatch.setattr("live_subs.desktop.probe", lambda _: ("stopped", False))
    return DesktopController(tmp_path)


def test_start_without_models_explains_preparation_and_spawns_no_process(controller, monkeypatch):
    spawn = Mock()
    monkeypatch.setattr("live_subs.desktop.subprocess.Popen", spawn)
    with pytest.raises(RuntimeError, match="Download"):
        controller.start_service()
    spawn.assert_not_called()
    assert not any(model["ready"] for model in controller.snapshot()["models"])


def test_repeated_start_owns_one_process_and_close_terminates_only_that_process(
    controller,
    monkeypatch,
):
    models_at(controller.directory)
    process = Mock()
    process.poll.return_value = None
    spawn = Mock(return_value=process)
    monkeypatch.setattr("live_subs.desktop.subprocess.Popen", spawn)
    controller.start_service()
    with pytest.raises(RuntimeError, match="in progress"):
        controller.start_service()
    assert controller.snapshot()["state"] == "starting"
    assert spawn.call_count == 1
    assert spawn.call_args.args[0][-1] == "serve"
    controller.close()
    process.terminate.assert_called_once()
    process.wait.assert_called_once_with(timeout=8)
    with pytest.raises(RuntimeError):
        controller.start_service()


def test_external_service_is_reported_but_stop_and_close_never_terminate_it(
    controller,
    monkeypatch,
):
    monkeypatch.setattr("live_subs.desktop.probe", lambda _: ("ready", True))
    spawn = Mock()
    monkeypatch.setattr("live_subs.desktop.subprocess.Popen", spawn)
    state = controller.snapshot()
    assert (state["state"], state["busy"], state["owned"]) == ("ready", True, False)
    with pytest.raises(RuntimeError, match="already in use"):
        controller.start_service()
    controller.stop_service()
    controller.close()
    spawn.assert_not_called()


def test_crashed_child_exposes_exit_status_and_redacts_pairing_secret_from_logs(
    controller,
    monkeypatch,
):
    models_at(controller.directory)
    process = Mock()
    process.poll.side_effect = [None, 7]
    process.returncode = 7
    monkeypatch.setattr("live_subs.desktop.subprocess.Popen", Mock(return_value=process))
    controller.start_service()
    (controller.directory / "desktop.log").write_text(f"failure {controller._token}")
    controller.snapshot()
    state = controller.snapshot()
    assert state["state"] == "error"
    assert state["error"] == "serve exited (7)"
    assert not state["owned"]
    assert controller._token not in json.dumps(state)
    assert "[redacted]" in state["logs"]


def test_unresponsive_owned_child_is_killed_after_graceful_shutdown_deadline(controller):
    process = Mock()
    process.poll.return_value = None
    process.wait.side_effect = [subprocess.TimeoutExpired("serve", 8), 0]
    controller._process = process
    controller.close()
    process.terminate.assert_called_once()
    process.kill.assert_called_once()
    assert process.wait.call_args_list[-1].kwargs == {"timeout": 5}


def test_parallel_preference_edits_preserve_both_fields_and_survive_a_new_controller(tmp_path):
    barrier = threading.Barrier(2)
    errors = []

    def save(patch):
        try:
            barrier.wait(timeout=2)
            update_preferences(tmp_path, patch)
        except Exception as exc:
            errors.append(exc)

    workers = [
        threading.Thread(target=save, args=(patch,))
        for patch in ({"language": "ja"}, {"fontSize": 32})
    ]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=3)
    assert not errors
    saved = read_preferences(tmp_path)
    assert saved == {
        "language": "ja",
        "display": "zh-en",
        "partials": True,
        "translate": True,
        "fontSize": 32,
    }


@pytest.mark.parametrize(
    "patch",
    [
        {"language": "de"},
        {"fontSize": True},
        {"fontSize": 41},
        {"fontSize": 17},
        {"partials": 1},
        {"translate": "false"},
        {"display": "ja-en"},
        {"token": "do-not-save"},
        [],
    ],
)
def test_invalid_caption_preferences_cannot_overwrite_saved_settings(tmp_path, patch):
    update_preferences(tmp_path, {"language": "ja"})
    with pytest.raises(ValueError):
        update_preferences(tmp_path, patch)
    assert read_preferences(tmp_path)["language"] == "ja"


def test_interface_language_and_theme_persist_and_unlisted_resources_are_rejected(controller):
    api = DesktopAPI(controller)
    api.save_interface({"locale": "en", "theme": "light"})
    assert DesktopAPI(DesktopController(controller.directory)).get_interface() == {
        "locale": "en",
        "theme": "light",
    }
    with pytest.raises(ValueError):
        api.open_resource("https://untrusted.example")
    with pytest.raises(ValueError):
        api.save_interface({"locale": "en", "theme": "invalid"})


def test_overlapping_window_shutdown_callbacks_terminate_owned_service_only_once(controller):
    process = Mock()
    process.poll.return_value = None
    entered = threading.Event()
    release = threading.Event()

    def terminate():
        entered.set()
        assert release.wait(timeout=2)

    process.terminate.side_effect = terminate
    controller._process = process
    first = threading.Thread(target=controller.close)
    first.start()
    assert entered.wait(timeout=1)
    try:
        controller.close()
        process.terminate.assert_called_once()
    finally:
        release.set()
        first.join(timeout=3)
    assert not first.is_alive()


def test_two_windows_cannot_prepare_models_or_truncate_logs_in_the_same_directory(
    controller,
    monkeypatch,
):
    process = Mock()
    process.poll.return_value = None
    spawn = Mock(return_value=process)
    monkeypatch.setattr("live_subs.desktop.subprocess.Popen", spawn)
    second = DesktopController(controller.directory)
    controller.prepare_models()
    log = controller.directory / "desktop.log"
    log.write_text("first window's download progress")
    with pytest.raises(RuntimeError, match="Another TingSub window"):
        second.prepare_models()
    assert spawn.call_count == 1
    assert log.read_text() == "first window's download progress"
    assert len(spawn.call_args.kwargs["pass_fds"]) == 1
    controller.close()
    second.prepare_models()
    assert spawn.call_count == 2
    second.close()


def test_translation_toggle_persists_without_changing_the_selected_target_languages(tmp_path):
    update_preferences(tmp_path, {"display": "source-zh", "translate": False})
    assert read_preferences(tmp_path)["translate"] is False
    assert read_preferences(tmp_path)["display"] == "source-zh"
    update_preferences(tmp_path, {"translate": True})
    assert read_preferences(tmp_path)["translate"] is True
    assert read_preferences(tmp_path)["display"] == "source-zh"


@pytest.mark.parametrize("exists", [False, True], ids=["before-first-log", "existing-log"])
def test_log_shortcut_reveals_current_file_or_opens_its_directory_without_creating_a_log(
    controller, monkeypatch, exists
):
    log = controller.directory / "desktop.log"
    if exists:
        log.write_text("diagnostic output")
    run = Mock()
    monkeypatch.setattr("live_subs.desktop.subprocess.run", run)
    assert DesktopAPI(controller).open_resource("logs") == {"ok": True}
    expected = (
        ["/usr/bin/open", "-R", str(log)]
        if exists
        else ["/usr/bin/open", str(controller.directory)]
    )
    run.assert_called_once_with(expected, check=True, timeout=3)
    assert log.exists() is exists
    if exists:
        assert log.read_text() == "diagnostic output"

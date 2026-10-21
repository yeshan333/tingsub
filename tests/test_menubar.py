from unittest.mock import Mock

import pytest

from live_subs.menubar import menu_state


def status(state="stopped", owned=False, busy=False):
    return {"state": state, "owned": owned, "busy": busy}


@pytest.mark.parametrize(
    "locale,expected", [("zh-CN", "正在生成字幕"), ("en", "Generating captions")]
)
def test_active_captions_show_localized_status_and_allow_stopping_owned_service(locale, expected):
    view = menu_state(status("ready", True, True), locale)
    assert view["status"] == expected
    assert view["enabled"]
    assert view["symbol"] == "captions.bubble.fill"


@pytest.mark.parametrize("state", ["stopping", "conflict"])
def test_service_action_is_disabled_while_stopping_or_port_is_occupied(state):
    assert not menu_state(status(state), "en")["enabled"]


def test_external_service_remains_visible_but_cannot_be_stopped_from_menu():
    view = menu_state(status("ready"), "en")
    assert view["status"] == "Ready for captions"
    assert view["service"] == "Managed by another window"
    assert not view["enabled"]


def test_owned_model_preparation_offers_cancel_instead_of_starting_another_service():
    view = menu_state(status("preparing", True), "en")
    assert view["service"] == "Cancel model preparation"
    assert view["enabled"]
    assert not menu_state(status("preparing", True), "en", working=True)["enabled"]


@pytest.mark.parametrize("service_state", ["ready", "conflict"])
def test_native_smoke_rejects_occupied_port_before_opening_window(
    tmp_path, monkeypatch, service_state
):
    import sys

    from live_subs import desktop_check

    launch = Mock()
    monkeypatch.setattr(
        sys, "argv", ["native-check", "--no-inference", "--data-dir", str(tmp_path)]
    )
    monkeypatch.setattr(desktop_check, "probe", lambda _: (service_state, False))
    monkeypatch.setattr(desktop_check, "launch", launch)
    with pytest.raises(SystemExit, match="Stop the existing local service"):
        desktop_check.main()
    launch.assert_not_called()

import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from live_subs.menubar import MenuBar, menu_state


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


@pytest.fixture
def menu():
    controller = Mock()
    controller._token = "private-token"
    controller.service_status.return_value = status()
    api = Mock()
    api.get_interface.return_value = {"locale": "en"}
    bar = MenuBar(Mock(), controller, api)
    bar.item = Mock()
    bar.items = {"service": Mock(), "quit": Mock()}
    bar.render = Mock()
    bar.dispatch = lambda call, *args: call(*args)
    bar.cocoa = SimpleNamespace(NSStatusBar=Mock(), NSApplication=Mock())
    return bar


def test_window_close_hides_without_stopping_service_and_show_restores_it(menu):
    assert menu.on_close() is False
    menu.window.hide.assert_called_once()
    menu.controller.close.assert_not_called()
    menu.controller.stop_service.assert_not_called()
    menu.show()
    menu.window.restore.assert_called_once()
    menu.window.show.assert_called_once()


def test_double_quit_stops_owned_work_once_before_destroying_window(menu):
    entered, release, destroyed = threading.Event(), threading.Event(), threading.Event()

    def close():
        entered.set()
        assert release.wait(3)

    menu.controller.close.side_effect = close
    menu.window.destroy.side_effect = destroyed.set
    menu.request_quit()
    assert entered.wait(1)
    menu.request_quit()
    menu.window.destroy.assert_not_called()
    assert menu.on_close() is True
    release.set()
    assert destroyed.wait(2)
    menu.controller.close.assert_called_once()
    menu.window.destroy.assert_called_once()
    assert menu.item is None


def test_menu_start_uses_fresh_state_and_never_stops_external_service(menu):
    finished = threading.Event()
    menu.controller.service_status.side_effect = lambda: (finished.set(), status("ready"))[1]
    menu.perform("service")
    assert finished.wait(1)
    assert menu._action_lock.acquire(timeout=1)
    menu._action_lock.release()
    menu.controller.start_service.assert_not_called()
    menu.controller.stop_service.assert_not_called()


def test_repeated_menu_click_does_not_start_duplicate_work(menu):
    entered, release = threading.Event(), threading.Event()

    def start():
        entered.set()
        assert release.wait(3)

    menu.controller.start_service.side_effect = start
    try:
        menu.perform("service")
        assert entered.wait(1)
        menu.perform("service")
        menu.controller.start_service.assert_called_once()
    finally:
        release.set()


def test_native_quit_acknowledges_macos_only_after_service_shutdown(menu):
    stopped, acknowledged = threading.Event(), threading.Event()
    menu.controller.close.side_effect = stopped.set
    app = menu.cocoa.NSApplication.sharedApplication()

    def reply(allowed):
        assert allowed is True and stopped.is_set()
        acknowledged.set()

    app.replyToApplicationShouldTerminate_.side_effect = reply
    menu.request_quit(native=True)
    assert acknowledged.wait(2)
    menu.controller.close.assert_called_once()
    menu.window.destroy.assert_not_called()

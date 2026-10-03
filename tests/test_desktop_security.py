import pytest

from live_subs.desktop_security import allowed_message, trusted_document

ENTRY = "http://127.0.0.1:23456/index.html"


@pytest.mark.parametrize(
    "url, main_frame",
    [
        ("https://example.com/", True),
        ("file:///tmp/foreign.html", True),
        ("data:text/html,foreign", True),
        ("http://127.0.0.1:23456/foreign.html", True),
        ("http://127.0.0.1:23457/index.html", True),
        (ENTRY + "?foreign", True),
        (ENTRY, False),
    ],
)
def test_navigation_cannot_replace_bundled_main_document_or_load_a_child_frame(url, main_frame):
    assert not trusted_document(url, ENTRY, main_frame)


def test_bundled_main_document_can_reload_and_reference_its_own_fragments():
    assert trusted_document(ENTRY, ENTRY, True)
    assert trusted_document(ENTRY + "#captions", ENTRY, True)


@pytest.mark.parametrize(
    "name",
    [
        "_controller._token.__str__",
        "snapshot.__self__._controller._token.__str__",
        "__class__.__str__",
        "pywebviewMoveWindow",
        "unknown",
    ],
)
def test_raw_bridge_messages_cannot_traverse_private_objects_or_call_unlisted_methods(name):
    body = {"funcName": name, "params": [], "id": "test"}
    assert not allowed_message(body, ENTRY, ENTRY, True, {"snapshot"})


def test_only_well_formed_main_frame_messages_can_call_an_exposed_method():
    body = {"funcName": "snapshot", "params": [], "id": "test"}
    assert allowed_message(body, ENTRY, ENTRY, True, {"snapshot"})
    assert not allowed_message(body, ENTRY, ENTRY, False, {"snapshot"})
    assert not allowed_message(body, "https://example.com", ENTRY, True, {"snapshot"})
    assert not allowed_message(body | {"params": {}}, ENTRY, ENTRY, True, {"snapshot"})
    assert not allowed_message(body | {"id": None}, ENTRY, ENTRY, True, {"snapshot"})

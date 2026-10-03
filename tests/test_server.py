import struct
import time

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from live_subs.server import create_app, token_at

ORIGIN = {"origin": "chrome-extension://" + "a" * 32}


class NoSpeechEngine:
    def transcribe(self, *_):
        raise AssertionError("Silence must not reach inference")


@pytest.fixture
def service(tmp_path):
    app = create_app(tmp_path, NoSpeechEngine)
    with TestClient(app) as client:
        yield client, token_at(tmp_path)


def test_unpaired_browser_cannot_start_audio_capture(service):
    client, _ = service
    with client.websocket_connect("/stream", headers=ORIGIN) as ws:
        ws.send_json({"token": "incorrect"})
        with pytest.raises(WebSocketDisconnect) as error:
            ws.receive_json()
        assert error.value.code == 1008
    assert not client.get("/health").json()["busy"]


def test_normal_website_cannot_connect_even_with_pairing_token(service):
    client, _ = service
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/stream", headers={"origin": "https://example.com"}):
            pytest.fail("Website connection was accepted")


def test_second_capture_is_rejected_until_first_capture_stops(service):
    client, token = service
    with client.websocket_connect("/stream", headers=ORIGIN) as first:
        first.send_json({"token": token})
        assert first.receive_json()["type"] == "ready"
        with client.websocket_connect("/stream", headers=ORIGIN) as second:
            second.send_json({"token": token})
            with pytest.raises(WebSocketDisconnect) as error:
                second.receive_json()
            assert error.value.code == 1013
        assert client.get("/health").json()["busy"]
        first.send_json({"type": "stop"})
        assert first.receive_json()["type"] == "done"
    with client.websocket_connect("/stream", headers=ORIGIN) as third:
        third.send_json({"token": token})
        assert third.receive_json()["type"] == "ready"
        third.send_json({"type": "stop"})
        assert third.receive_json()["type"] == "done"


def test_silent_audio_stops_cleanly_without_hallucinated_captions(service):
    client, token = service
    with client.websocket_connect("/stream", headers=ORIGIN) as ws:
        ws.send_json({"token": token})
        assert ws.receive_json()["type"] == "ready"
        epoch = time.time() * 1000 - 1000
        for index in range(50):
            ws.send_bytes(struct.pack("<d", epoch + (index + 1) * 20) + bytes(640))
        ws.send_json({"type": "stop"})
        assert ws.receive_json()["type"] == "done"


def test_malformed_audio_is_rejected_with_actionable_error(service):
    client, token = service
    with client.websocket_connect("/stream", headers=ORIGIN) as ws:
        ws.send_json({"token": token})
        ws.receive_json()
        ws.send_bytes(b"invalid")
        message = ws.receive_json()
        assert message["type"] == "error"
        assert "音频帧格式错误" in message["message"]


def test_pairing_secret_is_persistent_and_readable_only_by_owner(tmp_path):
    token = token_at(tmp_path)
    assert len(token) >= 32
    assert token_at(tmp_path) == token
    assert (tmp_path / "token").stat().st_mode & 0o777 == 0o600


def test_capture_resumes_after_timestamp_gap_without_treating_new_speech_as_expired(
    tmp_path,
    monkeypatch,
):
    voice = struct.pack("<h", 1000) * 320

    class SpeechVad:
        def __init__(self, *_):
            pass

        def is_speech(self, frame, *_):
            return frame == voice

    class SpeechEngine:
        def transcribe(self, pcm, language):
            assert pcm == voice * 15
            return "fresh speech", "en"

        def translate(self, text, language, display, on_chinese=None):
            return {"zh": "新鲜人声", "en": text}

    monkeypatch.setattr("live_subs.server.webrtcvad.Vad", SpeechVad)
    with TestClient(create_app(tmp_path, SpeechEngine)) as client:
        with client.websocket_connect("/stream", headers=ORIGIN) as ws:
            ws.send_json({"token": token_at(tmp_path), "partials": False})
            assert ws.receive_json()["type"] == "ready"
            now = time.time() * 1000
            for start in (now - 3600, now - 300):
                for n in range(15):
                    ws.send_bytes(struct.pack("<d", start + (n + 1) * 20) + voice)
            ws.send_json({"type": "stop"})
            events = []
            while (event := ws.receive_json())["type"] != "done":
                events.append(event)
    assert [e["id"] for e in events if e["type"] == "dropped"] == [1]
    assert [e["id"] for e in events if e["type"] == "translation"] == [2]
    assert sum(e["type"] == "notice" for e in events) == 1
    assert not any(e["type"] == "error" for e in events)


def test_caption_preferences_require_pairing_and_reject_ordinary_website_origins(service):
    client, token = service
    assert client.get("/preferences").status_code == 401
    assert client.patch("/preferences", json={"language": "ja"}).status_code == 401
    headers = {"authorization": f"Bearer {token}", "origin": "https://example.com"}
    assert client.patch("/preferences", headers=headers, json={"language": "ja"}).status_code == 403
    headers = {"authorization": f"Bearer {token}", **ORIGIN}
    assert client.get("/preferences", headers=headers).json()["language"] == "en"
    assert client.patch("/preferences", headers=headers, json={"language": "ja"}).status_code == 200
    assert client.get("/preferences", headers=headers).json()["language"] == "ja"


def test_invalid_shared_preferences_do_not_change_the_last_saved_caption_settings(service):
    client, token = service
    headers = {"authorization": f"Bearer {token}"}
    client.patch("/preferences", headers=headers, json={"fontSize": 32})
    assert client.patch("/preferences", headers=headers, json={"fontSize": 100}).status_code == 422
    assert client.patch("/preferences", headers=headers, content=b"invalid").status_code == 422
    assert client.patch("/preferences", headers=headers, content=b"x" * 1025).status_code == 413
    assert client.get("/preferences", headers=headers).json()["fontSize"] == 32

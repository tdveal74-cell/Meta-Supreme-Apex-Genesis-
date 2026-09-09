"""The presence service end to end over FastAPI's TestClient. No database.

Apps are built with ``create_app`` and an explicit ``PresenceSettings`` so the
DEVON JWTs minted here are signed with the same SECRET_KEY the app verifies
against. Streamers are scripted mocks and the audio clock is a
``VirtualPacer``, so a whole utterance drains in loop iterations rather than
seconds. The only real waits are the router's 20 ms first token threshold.
"""

import base64
import contextlib
import importlib
import json
import time
from typing import Any, Callable, Dict, List

import jwt
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import apps.presence.main as presence_main
from apps.presence.inference import MockTokenStreamer
from apps.presence.livekit_token import decode_livekit_token
from apps.presence.main import TTS_TEXT_LIMIT, SpeakRequest, create_app
from apps.presence.protocol import AUDIO_CODEC, AUDIO_RATE, PRIORITY_OF, validate_frame
from apps.presence.session import VirtualPacer
from apps.presence.settings import PresenceConfigError, PresenceSettings
from apps.presence.speech import MockSpeech

TEST_SECRET = "presence-test-secret-0123456789abcdef0123456789abcdef"
REPLY = "Hello there. How are you today?"

SETTINGS = PresenceSettings(
    SECRET_KEY=TEST_SECRET, ENVIRONMENT="test", PRESENCE_TTFT_THRESHOLD_MS=20
)


def mint(secret: str = TEST_SECRET, **claims: Any) -> str:
    now = int(time.time())
    payload: Dict[str, Any] = {"sub": "user-1", "type": "access", "iat": now, "exp": now + 600}
    payload.update(claims)
    return jwt.encode(payload, secret, algorithm="HS256")


def hello(ws, token: str) -> Dict[str, Any]:
    ws.send_json({"t": "hello", "token": token, "client": "web", "protocol": 1})
    return ws.receive_json()


def collect_until(ws, stop: Callable[[Dict[str, Any]], bool], limit: int = 5000) -> List[Dict[str, Any]]:
    messages: List[Dict[str, Any]] = []
    while len(messages) < limit:
        message = ws.receive_json()
        messages.append(message)
        if stop(message):
            return messages
    raise AssertionError(f"no stop message within {limit} frames")


def is_listening(message: Dict[str, Any]) -> bool:
    return message["t"] == "state" and message["state"] == "listening"


def run_turn(ws, turn_id: str, text: str) -> List[Dict[str, Any]]:
    ws.send_json({"t": "say", "turn_id": turn_id, "text": text})
    return collect_until(ws, is_listening)


def fast_app(**overrides: Any) -> TestClient:
    kwargs: Dict[str, Any] = {
        "primary": MockTokenStreamer(REPLY, name="mock"),
        "speech": MockSpeech(),
        "pacer": VirtualPacer(),
    }
    kwargs.update(overrides)
    settings = kwargs.pop("settings", SETTINGS)
    return TestClient(create_app(settings, **kwargs))


@contextlib.contextmanager
def open_ready(client: TestClient):
    """A connected, authenticated socket that has already reached ``listening``."""
    with client.websocket_connect("/ws/presence") as ws:
        ready = hello(ws, mint())
        assert ready["t"] == "ready"
        assert is_listening(ws.receive_json())
        yield ws


# ---------------------------------------------------------------------------
# health and settings
# ---------------------------------------------------------------------------


def test_health_reports_wiring_and_breaker():
    client = fast_app()
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "devon-presence"
    assert body["inference"] == "mock"
    assert body["fallback"] == ""
    assert body["speech"] == "mock"
    assert body["livekit_configured"] is False
    assert body["audio_over_websocket"] is True
    assert body["breaker"]["state"] == "closed"
    assert body["breaker"]["ttft_threshold_ms"] == 20.0

    # cors_origins was added on 2026-09-09 because a localhost only list makes
    # the chat's POST /tts fail silently: the browser discards a 200 and DEVON
    # goes quiet with no error anywhere. A critic then found nothing asserted it,
    # so the one readback that diagnoses that failure could vanish unnoticed.
    assert body["cors_origins"] == [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    # The readback is only useful if it is the real list rather than a literal.
    assert body["cors_origins"] == list(
        PresenceSettings.from_env({}).PRESENCE_CORS_ORIGINS
    )


def test_health_says_only_these_things_and_no_more():
    """
    /health is unauthenticated, so its key set is a disclosure surface and not
    only a convenience. Pinned exactly, the way test_deploy_soul.py:224 pins the
    soul host's, so a field added here is a deliberate decision rather than
    something that arrives with a debugging session and stays. The values are the
    estate's public web origins and its provider names; a preview origin or an
    internal hostname joining that list is the case that would matter.
    """
    body = fast_app().get("/health").json()
    assert set(body) == {
        "status",
        "service",
        "inference",
        "fallback",
        "speech",
        "cors_origins",
        "livekit_configured",
        "audio_over_websocket",
        "breaker",
    }
    # And nothing that reads like a credential, at any nesting depth.
    flat = repr(body).lower()
    for mark in ("key", "secret", "token", "password", "authorization"):
        assert mark not in flat, f"/health leaks something named {mark}"


def test_settings_refuse_the_public_default_and_an_empty_key_when_deployed():
    with pytest.raises(PresenceConfigError, match="public default"):
        PresenceSettings.from_env({"ENVIRONMENT": "production"})
    with pytest.raises(PresenceConfigError, match="empty"):
        PresenceSettings.from_env({"ENVIRONMENT": "staging", "SECRET_KEY": ""})
    with pytest.raises(PresenceConfigError, match="RAILWAY_PROJECT_ID"):
        PresenceSettings.from_env({"ENVIRONMENT": "", "RAILWAY_PROJECT_ID": "p"})
    ok = PresenceSettings.from_env({"ENVIRONMENT": "production", "SECRET_KEY": TEST_SECRET})
    assert ok.SECRET_KEY == TEST_SECRET
    local = PresenceSettings.from_env({"ENVIRONMENT": "development"})
    assert local.PRESENCE_INFERENCE == "mock" and local.PRESENCE_WINDOW_MS == 250


def test_settings_refuse_bad_values_by_name():
    base = {"ENVIRONMENT": "test"}
    with pytest.raises(PresenceConfigError, match="PRESENCE_INFERENCE"):
        PresenceSettings.from_env({**base, "PRESENCE_INFERENCE": "gemini"})
    with pytest.raises(PresenceConfigError, match="names the primary"):
        PresenceSettings.from_env({**base, "PRESENCE_FALLBACK_INFERENCE": "mock"})
    with pytest.raises(PresenceConfigError, match="PRESENCE_SPEECH"):
        PresenceSettings.from_env({**base, "PRESENCE_SPEECH": "elevenlabs"})
    with pytest.raises(PresenceConfigError, match="PRESENCE_TTFT_THRESHOLD_MS"):
        PresenceSettings.from_env({**base, "PRESENCE_TTFT_THRESHOLD_MS": "fast"})
    with pytest.raises(PresenceConfigError, match="PRESENCE_WINDOW_MS"):
        PresenceSettings.from_env({**base, "PRESENCE_WINDOW_MS": "0"})
    with pytest.raises(PresenceConfigError, match="LIVEKIT_API_SECRET"):
        PresenceSettings.from_env({**base, "LIVEKIT_URL": "wss://x", "LIVEKIT_API_KEY": "k"})
    with pytest.raises(PresenceConfigError, match="PRESENCE_CORS_ORIGINS"):
        PresenceSettings.from_env({**base, "PRESENCE_CORS_ORIGINS": "http://localhost:3000"})
    parsed = PresenceSettings.from_env(
        {**base, "PRESENCE_CORS_ORIGINS": '["https://a.example", "https://b.example"]'}
    )
    assert parsed.PRESENCE_CORS_ORIGINS == ("https://a.example", "https://b.example")


# ---------------------------------------------------------------------------
# hello
# ---------------------------------------------------------------------------


def test_hello_with_a_bad_token_closes_4401():
    client = fast_app()
    with client.websocket_connect("/ws/presence") as ws:
        error = hello(ws, mint(secret="not-the-secret-0123456789abcdef0123456789abcdef"))
        assert error["t"] == "error" and error["code"] == 4401
        with pytest.raises(WebSocketDisconnect) as info:
            ws.receive_json()
        assert info.value.code == 4401


def test_hello_with_a_non_access_token_closes_4401():
    client = fast_app()
    with client.websocket_connect("/ws/presence") as ws:
        error = hello(ws, mint(type="refresh"))
        assert error["code"] == 4401
        with pytest.raises(WebSocketDisconnect) as info:
            ws.receive_json()
        assert info.value.code == 4401


def test_malformed_hello_closes_4400():
    client = fast_app()
    with client.websocket_connect("/ws/presence") as ws:
        ws.send_text("this is not json")
        error = ws.receive_json()
        assert error["t"] == "error" and error["code"] == 4400
        with pytest.raises(WebSocketDisconnect) as info:
            ws.receive_json()
        assert info.value.code == 4400

    with client.websocket_connect("/ws/presence") as ws:
        ws.send_json({"t": "hello", "token": mint(), "client": "web", "protocol": 2})
        error = ws.receive_json()
        assert error["code"] == 4400 and "protocol" in error["message"]
        with pytest.raises(WebSocketDisconnect) as info:
            ws.receive_json()
        assert info.value.code == 4400


def test_good_hello_returns_ready_then_listening():
    client = fast_app()
    with client.websocket_connect("/ws/presence") as ws:
        ready = hello(ws, mint())
        assert ready["t"] == "ready"
        assert ready["protocol"] == 1
        assert ready["speech"] == "mock"
        assert ready["inference"] == "mock"
        assert ready["fallback"] == ""
        assert ready["livekit"] == {"configured": False, "url": None}
        assert len(ready["session_id"]) == 32
        state = ws.receive_json()
        assert state["t"] == "state" and state["state"] == "listening"
        assert state["turn_id"] is None and state["at_ms"] > 0


# ---------------------------------------------------------------------------
# turns
# ---------------------------------------------------------------------------


def test_say_streams_tokens_frames_audio_and_metrics():
    client = fast_app()
    with open_ready(client) as ws:
        messages = run_turn(ws, "turn-1", "hello DEVON")

    states = [(m["state"], m["turn_id"]) for m in messages if m["t"] == "state"]
    assert states == [("thinking", "turn-1"), ("speaking", "turn-1"), ("listening", None)]

    tokens = [m for m in messages if m["t"] == "token"]
    assert "".join(m["text"] for m in tokens) == REPLY
    assert all(m["turn_id"] == "turn-1" for m in tokens)

    frames = [m for m in messages if m["t"] == "frame"]
    assert len(frames) >= 1
    for frame in frames:
        assert frame["turn_id"] == "turn-1"
        assert frame["priority"] in (0, 1, 2)
        assert validate_frame(frame["weights"]) == frame["weights"]
        assert all(name in PRIORITY_OF for name in frame["weights"])
    at_ms = [frame["at_ms"] for frame in frames]
    assert at_ms == sorted(at_ms), "frames must leave in audio timeline order"
    assert at_ms[-1] > at_ms[0]
    seqs = [frame["seq"] for frame in frames]
    assert len(set(seqs)) == len(seqs)
    assert any(frame["priority"] == 1 for frame in frames), "a blink frame was expected"
    assert any(frame["weights"].get("jawOpen", 0) >= 0.35 for frame in frames)

    audio = [m for m in messages if m["t"] == "audio"]
    assert audio, "LiveKit is not configured, so audio must travel on the socket"
    assert all(a["codec"] == "pcm_s16le" and a["rate"] == 16000 for a in audio)
    assert [a["seq"] for a in audio] == list(range(len(audio)))
    assert [a["at_ms"] for a in audio] == sorted(a["at_ms"] for a in audio)

    metrics = [m for m in messages if m["t"] == "metrics"]
    assert len(metrics) == 1
    metric = metrics[0]
    assert metric["turn_id"] == "turn-1"
    assert metric["provider"] == "mock"
    assert metric["fell_back"] is False
    assert metric["ttft_ms"] >= 0
    assert metric["breaker"] == "closed"
    assert metric["frames_sent"] == len(frames)
    assert metric["frames_dropped"] == 0
    assert metric["tokens"] == len(tokens)
    # Metrics are the last thing before the session says it is listening again.
    assert messages.index(metric) == len(messages) - 2


def test_interrupt_mid_turn_acks_flushes_and_returns_to_listening():
    # A pacer that never advances holds the turn in flight after the first
    # window of frames has left, so the interrupt lands mid utterance.
    client = fast_app(pacer=VirtualPacer(auto_advance=False))
    with open_ready(client) as ws:
        ws.send_json({"t": "say", "turn_id": "turn-2", "text": "talk to me"})
        before = collect_until(ws, lambda m: m["t"] == "frame")
        assert ("speaking", "turn-2") in [
            (m["state"], m["turn_id"]) for m in before if m["t"] == "state"
        ]

        ws.send_json({"t": "interrupt", "turn_id": "turn-2", "at_ms": 1234.5})
        until_ack = collect_until(ws, lambda m: m["t"] == "interrupt_ack")
        ack = until_ack[-1]
        assert ack["turn_id"] == "turn-2"
        assert ack["flushed_frames"] >= 0
        assert ack["server_latency_ms"] >= 0
        assert ack["server_latency_ms"] < 1000
        frames_seen = sum(1 for m in before + until_ack if m["t"] == "frame")
        assert frames_seen + ack["flushed_frames"] >= 1

        after = ws.receive_json()
        assert after["t"] == "state" and after["state"] == "listening"
        metric = ws.receive_json()
        assert metric["t"] == "metrics" and metric["turn_id"] == "turn-2"
        assert metric["frames_sent"] == frames_seen
        assert metric["frames_dropped"] == ack["flushed_frames"]

        # The socket is still up and the session still answers.
        ws.send_json({"t": "ping", "at_ms": 42})
        pong = ws.receive_json()
        assert pong["t"] == "pong" and pong["at_ms"] == 42 and pong["server_ms"] > 0


def test_interrupt_for_another_turn_acks_without_cancelling():
    client = fast_app(pacer=VirtualPacer(auto_advance=False))
    with open_ready(client) as ws:
        ws.send_json({"t": "say", "turn_id": "turn-3", "text": "keep going"})
        collect_until(ws, lambda m: m["t"] == "frame")
        ws.send_json({"t": "interrupt", "turn_id": "someone-else", "at_ms": 1})
        ack = collect_until(ws, lambda m: m["t"] == "interrupt_ack")[-1]
        assert ack["flushed_frames"] == 0
        state = ws.receive_json()
        assert state["t"] == "state" and state["state"] == "listening"
        # A real interrupt for the live turn still finds it in flight.
        ws.send_json({"t": "interrupt", "turn_id": "turn-3", "at_ms": 2})
        ack = collect_until(ws, lambda m: m["t"] == "interrupt_ack")[-1]
        assert ack["turn_id"] == "turn-3"
        assert collect_until(ws, lambda m: m["t"] == "metrics")[-1]["turn_id"] == "turn-3"


def test_router_falls_back_on_the_same_connection_without_disconnecting():
    slow = MockTokenStreamer("slow primary reply", first_token_delay_ms=200, name="slow")
    fallback = MockTokenStreamer("fallback reply here", name="fallback")
    client = fast_app(primary=slow, fallback=fallback)

    with open_ready(client) as ws:
        first = run_turn(ws, "turn-4", "first question")
        assert "".join(m["text"] for m in first if m["t"] == "token") == "fallback reply here"
        metric = [m for m in first if m["t"] == "metrics"][0]
        assert metric["provider"] == "fallback"
        assert metric["fell_back"] is True
        assert metric["ttft_ms"] >= 20
        assert metric["breaker"] == "closed"
        assert len([m for m in first if m["t"] == "frame"]) >= 1

        # Same socket, second turn: the session was never dropped.
        second = run_turn(ws, "turn-5", "second question")
        assert [m for m in second if m["t"] == "metrics"][0]["fell_back"] is True
        ws.send_json({"t": "ping", "at_ms": 7})
        assert ws.receive_json()["t"] == "pong"

        assert client.get("/health").json()["breaker"]["consecutive_breaches"] == 2
        third = run_turn(ws, "turn-6", "third question")
        assert [m for m in third if m["t"] == "metrics"][0]["breaker"] == "open"

    health = client.get("/health").json()["breaker"]
    assert health["state"] == "open"
    assert health["opens"] == 1
    assert slow.calls == 3 and fallback.calls == 3


def test_no_fallback_reports_an_error_and_keeps_listening():
    broken = MockTokenStreamer(fail_before_first=True, name="broken")
    client = fast_app(primary=broken)
    with open_ready(client) as ws:
        messages = run_turn(ws, "turn-7", "anyone there")
        errors = [m for m in messages if m["t"] == "error"]
        assert len(errors) == 1 and errors[0]["code"] == 4500
        assert "PRESENCE_FALLBACK_INFERENCE" in errors[0]["message"]
        assert [m for m in messages if m["t"] == "metrics"][0]["tokens"] == 0
        ws.send_json({"t": "ping", "at_ms": 1})
        assert ws.receive_json()["t"] == "pong"


def test_render_report_drives_compression():
    client = fast_app()
    with open_ready(client) as ws:
        baseline = [m for m in run_turn(ws, "turn-8", "baseline") if m["t"] == "metrics"][0]
        ws.send_json({"t": "render", "turn_id": "turn-9", "behind_ms": 5000, "fps": 12})
        compressed = run_turn(ws, "turn-9", "baseline")
        metric = [m for m in compressed if m["t"] == "metrics"][0]

    assert baseline["frames_dropped"] == 0
    assert metric["frames_dropped"] > 0
    assert metric["frames_sent"] < baseline["frames_sent"]
    assert metric["frames_sent"] + metric["frames_dropped"] == baseline["frames_sent"]
    assert len([m for m in compressed if m["t"] == "audio"]) > 0, "audio is never dropped"


def test_malformed_messages_after_hello_get_an_error_and_keep_the_socket():
    client = fast_app()
    with open_ready(client) as ws:
        ws.send_json({"t": "nope"})
        error = ws.receive_json()
        assert error["t"] == "error" and error["code"] == 4400
        ws.send_json({"t": "say", "turn_id": "x", "text": ""})
        assert ws.receive_json()["code"] == 4400
        ws.send_json({"t": "hello", "token": mint(), "protocol": 1})
        assert "already authenticated" in ws.receive_json()["message"]
        ws.send_json({"t": "ping", "at_ms": 3})
        assert ws.receive_json()["t"] == "pong"


def test_say_while_speaking_barges_in():
    client = fast_app(pacer=VirtualPacer(auto_advance=False))
    with open_ready(client) as ws:
        ws.send_json({"t": "say", "turn_id": "turn-10", "text": "first"})
        collect_until(ws, lambda m: m["t"] == "frame")
        ws.send_json({"t": "say", "turn_id": "turn-11", "text": "second"})
        messages = collect_until(ws, lambda m: m["t"] == "state" and m["state"] == "thinking")
        metric = [m for m in messages if m["t"] == "metrics"]
        assert metric and metric[-1]["turn_id"] == "turn-10"
        assert messages[-1]["turn_id"] == "turn-11"


# ---------------------------------------------------------------------------
# LiveKit
# ---------------------------------------------------------------------------


def test_livekit_token_needs_auth_and_names_the_gate_when_unconfigured():
    client = fast_app()
    assert client.post("/livekit/token", json={"room": "r"}).status_code == 401
    bad = client.post(
        "/livekit/token",
        json={"room": "r"},
        headers={"Authorization": f"Bearer {mint(secret='wrong-secret-0123456789abcdef0123456789abcdef')}"},
    )
    assert bad.status_code == 401
    response = client.post(
        "/livekit/token", json={"room": "r"}, headers={"Authorization": f"Bearer {mint()}"}
    )
    assert response.status_code == 503
    assert "LIVEKIT_URL" in response.json()["detail"]


def test_livekit_token_mints_when_configured_and_audio_leaves_the_socket():
    settings = PresenceSettings(
        SECRET_KEY=TEST_SECRET,
        ENVIRONMENT="test",
        PRESENCE_TTFT_THRESHOLD_MS=20,
        LIVEKIT_URL="wss://example.livekit.cloud",
        LIVEKIT_API_KEY="APIkey",
        LIVEKIT_API_SECRET="livekit-secret-0123456789abcdef0123456789abcdef",
    )
    client = fast_app(settings=settings)

    # A room the caller has no presence session for is refused: the token
    # would otherwise let one signed-in user join any room the estate's
    # LiveKit project holds.
    foreign = client.post(
        "/livekit/token", json={"room": "devon"}, headers={"Authorization": f"Bearer {mint()}"}
    )
    assert foreign.status_code == 403
    assert "session_id" in foreign.json()["detail"]

    assert client.get("/health").json()["audio_over_websocket"] is False
    with client.websocket_connect("/ws/presence") as ws:
        ready = hello(ws, mint())
        assert ready["livekit"] == {"configured": True, "url": "wss://example.livekit.cloud"}
        ws.receive_json()
        room = ready["session_id"]

        response = client.post(
            "/livekit/token", json={"room": room}, headers={"Authorization": f"Bearer {mint()}"}
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["url"] == "wss://example.livekit.cloud"
        assert body["room"] == room
        assert body["identity"] == "user-1"
        assert body["expires_at"].endswith("Z")
        claims = decode_livekit_token(
            body["token"], "APIkey", "livekit-secret-0123456789abcdef0123456789abcdef"
        )
        assert claims["sub"] == "user-1" and claims["video"]["room"] == room

        # The identity is the verified user, never a caller's choice: a
        # supplied identity is ignored rather than honoured.
        other = client.post(
            "/livekit/token",
            json={"room": room, "identity": "tee-laptop"},
            headers={"Authorization": f"Bearer {mint()}"},
        ).json()
        assert other["identity"] == "user-1"

        # Another signed-in user cannot mint for this session's room.
        stranger = client.post(
            "/livekit/token",
            json={"room": room},
            headers={"Authorization": f"Bearer {mint(sub='user-2')}"},
        )
        assert stranger.status_code == 403

        messages = run_turn(ws, "turn-12", "hi")
        assert not [m for m in messages if m["t"] == "audio"]
        assert [m for m in messages if m["t"] == "frame"]

    # The session is forgotten when the socket closes, so the room dies with it.
    closed = client.post(
        "/livekit/token", json={"room": room}, headers={"Authorization": f"Bearer {mint()}"}
    )
    assert closed.status_code == 403


class _HostileSpeech:
    """A synthesiser that puts a frame off the end of time, then a NaN."""

    name = "hostile"

    def __init__(self, at_ms: float) -> None:
        self._at_ms = at_ms

    async def synthesize(self, text: str, turn: str):
        from apps.presence.speech import CHUNK_FRAME, CHUNK_STATE, STATE_SPEAKING, SpeechChunk

        yield SpeechChunk(kind=CHUNK_STATE, at_ms=0.0, state=STATE_SPEAKING)
        yield SpeechChunk(kind=CHUNK_FRAME, at_ms=0.0, weights={"jawOpen": 0.5})
        yield SpeechChunk(kind=CHUNK_FRAME, at_ms=self._at_ms, weights={"jawOpen": 0.6})


@pytest.mark.parametrize("at_ms", [float("inf"), float("nan"), -5.0])
def test_a_frame_off_the_timeline_fails_the_turn_by_name_and_never_reaches_the_wire(at_ms):
    """An infinite at_ms held the drain loop open forever and a NaN went out
    as a token JSON does not have. Both now fail the turn with an error that
    names the value, and the session lands back on listening."""
    client = fast_app(speech=_HostileSpeech(at_ms))
    with open_ready(client) as ws:
        ws.send_json({"t": "say", "turn_id": "turn-hostile", "text": "hi"})
        messages = collect_until(ws, is_listening)
    errors = [m for m in messages if m["t"] == "error"]
    assert errors, messages
    assert "at_ms" in errors[0]["message"]
    for message in messages:
        if message["t"] == "frame":
            assert message["at_ms"] == 0.0


# ---------------------------------------------------------------------------
# the default app reads the environment
# ---------------------------------------------------------------------------


def test_default_app_verifies_against_secret_key_from_the_environment(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", TEST_SECRET)
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.delenv("PRESENCE_INFERENCE", raising=False)
    monkeypatch.delenv("PRESENCE_FALLBACK_INFERENCE", raising=False)
    monkeypatch.delenv("PRESENCE_SPEECH", raising=False)
    module = importlib.reload(presence_main)
    try:
        client = TestClient(module.app)
        assert client.get("/health").json()["inference"] == "mock"
        with client.websocket_connect("/ws/presence") as ws:
            assert hello(ws, mint())["t"] == "ready"
        with client.websocket_connect("/ws/presence") as ws:
            assert hello(ws, mint(secret="another-secret-0123456789abcdef0123456789abcdef"))["code"] == 4401
            with pytest.raises(WebSocketDisconnect):
                ws.receive_json()
    finally:
        monkeypatch.undo()
        importlib.reload(presence_main)


@pytest.mark.parametrize(
    "raw",
    ['{"t":"ping","at_ms":NaN}', '{"t":"render","turn_id":"t","behind_ms":Infinity,"fps":60}'],
)
def test_non_finite_numbers_from_the_client_are_refused_by_name(raw):
    """json.loads admits NaN and Infinity. A NaN ping used to kill the socket
    on the way back out and an infinite behind_ms poisoned every later turn."""
    client = fast_app()
    with open_ready(client) as ws:
        ws.send_text(raw)
        reply = ws.receive_json()
        assert reply["t"] == "error"
        assert "finite" in reply["message"]
        # The socket is still alive and a turn still runs.
        messages = run_turn(ws, "turn-after-nan", "hi")
        assert [m for m in messages if m["t"] == "frame"]


def test_an_integer_too_large_for_a_float_is_refused_by_name_and_the_socket_lives():
    huge = "9" * 400
    client = fast_app()
    with open_ready(client) as ws:
        for raw in (
            '{"t":"ping","at_ms":' + huge + "}",
            '{"t":"render","turn_id":"t","behind_ms":' + huge + ',"fps":60}',
        ):
            ws.send_text(raw)
            reply = ws.receive_json()
            assert reply["t"] == "error"
            assert "finite" in reply["message"]
        messages = run_turn(ws, "turn-after-huge", "hi")
        assert [m for m in messages if m["t"] == "frame"]


# ---------------------------------------------------------------------------
# POST /tts: DEVON's voice on a surface that has no socket.
#
# WHY THIS ROUTE EXISTS. Tee opened /devon on 2026-09-09 and DEVON answered in
# a stock female browser voice, because DevonChat called
# window.speechSynthesis and took whatever the machine had installed. Two
# surfaces spoke as DEVON in two voices and only /presence used the clone. The
# estate's standing rule is voice and identity owned, never rented, with no
# exception path, so the chat now borrows this service's voice.
#
# The rules under test are the ones that keep it owned: it is authenticated,
# the caller cannot name a voice, and the wire format is the socket's own audio
# message so the browser decodes it with tested code rather than a second copy.
# ---------------------------------------------------------------------------


def _ndjson(response) -> List[Dict[str, Any]]:
    return [json.loads(line) for line in response.text.splitlines() if line.strip()]


def test_tts_refuses_without_a_token():
    client = fast_app()
    response = client.post("/tts", json={"text": "hello"})
    assert response.status_code == 401
    assert "Bearer" in response.json()["detail"]


def test_tts_refuses_a_token_signed_with_another_secret():
    client = fast_app()
    response = client.post(
        "/tts",
        json={"text": "hello"},
        headers={"Authorization": f"Bearer {mint(secret='a-different-secret-entirely-0123456789')}"},
    )
    assert response.status_code == 401


def test_tts_streams_the_socket_s_own_audio_message_shape():
    client = fast_app()
    response = client.post(
        "/tts",
        json={"text": REPLY},
        headers={"Authorization": f"Bearer {mint()}"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")
    messages = _ndjson(response)
    assert messages, "no audio was streamed"
    for message in messages:
        # Same keys the websocket sends, because the browser reuses one decoder.
        assert message["t"] == "audio"
        assert message["codec"] == AUDIO_CODEC
        assert message["rate"] == AUDIO_RATE
        assert isinstance(message["b64"], str) and message["b64"]
        base64.b64decode(message["b64"])
    # Sequence numbers are dense and ordered, or a dropped chunk is invisible.
    assert [m["seq"] for m in messages] == list(range(1, len(messages) + 1))


def test_tts_names_the_adapter_on_the_response():
    """Silence from the mock adapter and silence from a broken key look alike.

    The header is the only way a caller can tell which one it got without
    decoding audio, and a reader who cannot tell will report mock as working.
    """
    client = fast_app()
    response = client.post(
        "/tts", json={"text": "hello"}, headers={"Authorization": f"Bearer {mint()}"}
    )
    assert response.headers["x-devon-speech"] == "mock"


def test_tts_emits_no_face_frames():
    """The chat has no avatar, so frames would be bytes nobody reads."""
    client = fast_app()
    response = client.post(
        "/tts", json={"text": REPLY}, headers={"Authorization": f"Bearer {mint()}"}
    )
    assert all(m["t"] == "audio" for m in _ndjson(response))


def test_tts_refuses_an_empty_or_oversized_utterance():
    client = fast_app()
    auth = {"Authorization": f"Bearer {mint()}"}
    assert client.post("/tts", json={"text": ""}, headers=auth).status_code == 422
    over = "x" * (TTS_TEXT_LIMIT + 1)
    assert client.post("/tts", json={"text": over}, headers=auth).status_code == 422


def test_the_caller_can_never_choose_the_voice():
    """The rule this holds shut is a compliance one, not a preference.

    A voice field on this endpoint would make it a rented-persona service: any
    signed-in caller could speak as anybody Cartesia will synthesise. The voice
    is CARTESIA_VOICE_ID on this service and nowhere else, so the request model
    must carry no voice field at all and must not quietly accept one.
    """
    assert set(SpeakRequest.model_fields) == {"text"}
    assert "voice" not in str(SpeakRequest.model_fields).lower()

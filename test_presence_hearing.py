"""Protocol v2: the presence socket gets an ear.

Two properties here are worth more than the rest of the file, and each is
written as the incident it would be rather than as a style check:

1. **A v1 client keeps working across this deploy.** ``protocol.py`` refused
   any hello that was not the server's own version, and
   ``apps/web/lib/presence/protocol.ts:243`` refuses any ``ready`` that is not
   the client's own. Those pins face each other and the two services deploy
   separately, so a server that simply announced 2 would black out every page
   built against 1, in both directions, until the web app caught up.
   ``test_a_v1_hello_is_answered_with_one`` is that outage written down.

2. **Speaking a turn and typing one converge.** The transcript goes into the
   same ``begin_turn`` a ``say`` enters, so v2 adds nothing that can act that
   typing could not already. That is checked behaviourally, by running the
   same utterance both ways and comparing what comes back, and structurally,
   by reading ``_handle_listen``'s own AST for a call outside the allowlist.
   The second survives a refactor the first would not notice.

The ElevenLabs adapter is exercised against an httpx MockTransport, the same
way ``test_presence_cartesia.py`` does it, because the vendor is unreachable
from CI and a test that needs a key is a test that does not run.
"""

import ast
import base64
import inspect
import io
import json
import time
import wave
from typing import Any, Dict, List

import httpx
import jwt
import pytest
from fastapi.testclient import TestClient

from apps.presence.hearing import (
    ELEVENLABS_STT_MODELS,
    ELEVENLABS_STT_URL,
    ClipInProgress,
    ClipTooLarge,
    ElevenLabsHearing,
    HeardClip,
    HearingFailed,
    HearingNotConfigured,
    MockHearing,
    _confidence_of,
    build_hearing,
    upload_for,
    wav_from_pcm,
)
from apps.presence.inference import MockTokenStreamer
from apps.presence.main import _handle_listen, create_app
from apps.presence.protocol import (
    ERR_CLIP_TOO_LARGE,
    ERR_HEARING_FAILED,
    ERR_MALFORMED,
    ERR_PROTOCOL_TOO_OLD,
    MAX_CLIP_BYTES,
    MAX_CLIP_CHUNKS,
    MAX_MESSAGE_CHARS,
    PROTOCOL_VERSION,
    SUPPORTED_PROTOCOLS,
)
from apps.presence.session import VirtualPacer
from apps.presence.settings import PresenceConfigError, PresenceSettings
from apps.presence.speech import MockSpeech

TEST_SECRET = "presence-test-secret-0123456789abcdef0123456789abcdef"
REPLY = "Hello there. How are you today?"
SPOKEN = "what time is it"

#: Not a real key anywhere. The repository is public.
FAKE_KEY = "test-elevenlabs-key-not-a-real-one"

SETTINGS = PresenceSettings(
    SECRET_KEY=TEST_SECRET, ENVIRONMENT="test", PRESENCE_TTFT_THRESHOLD_MS=20
)


def mint() -> str:
    now = int(time.time())
    return jwt.encode(
        {"sub": "user-1", "type": "access", "iat": now, "exp": now + 600},
        TEST_SECRET,
        algorithm="HS256",
    )


def fast_app(**overrides: Any) -> TestClient:
    kwargs: Dict[str, Any] = {
        "primary": MockTokenStreamer(REPLY, name="mock"),
        "speech": MockSpeech(),
        "hearing": MockHearing([SPOKEN]),
        "pacer": VirtualPacer(),
    }
    kwargs.update(overrides)
    return TestClient(create_app(SETTINGS, **kwargs))


def hello(ws, protocol: int = 2) -> Dict[str, Any]:
    """Handshake, and swallow the opening state frame.

    ``PresenceSession.open`` emits ``state: listening`` immediately after
    ``ready``. Leaving it in the stream makes every later ``receive_json``
    read a state frame where the test meant to read an error, which fails as
    a KeyError on 'code' and reads like the error never arrived.
    """
    ws.send_json({"t": "hello", "token": mint(), "client": "web", "protocol": protocol})
    ready = ws.receive_json()
    if ready["t"] == "ready":
        opening = ws.receive_json()
        assert opening["t"] == "state" and opening["state"] == "listening", opening
    return ready


def drain_to_listening(ws, limit: int = 5000) -> List[Dict[str, Any]]:
    messages: List[Dict[str, Any]] = []
    while len(messages) < limit:
        message = ws.receive_json()
        messages.append(message)
        if message["t"] == "state" and message["state"] == "listening":
            return messages
    raise AssertionError(f"no listening state within {limit} frames")


def speak(ws, turn_id: str, audio: bytes, *, codec: str = "pcm_s16le", rate: int = 16000):
    ws.send_json({"t": "listen_start", "turn_id": turn_id, "codec": codec, "rate": rate})
    ws.send_json(
        {
            "t": "listen_chunk",
            "turn_id": turn_id,
            "seq": 0,
            "b64": base64.b64encode(audio).decode(),
        }
    )
    ws.send_json({"t": "listen_end", "turn_id": turn_id})


CLIP = b"\x00\x01" * 400


# ---------------------------------------------------------------------------
# The deploy does not black out the page


def test_a_v1_hello_is_answered_with_one():
    """The load bearing test.

    If this ever returns 2, every browser running the current web client
    drops the ready frame and the presence page stops connecting, while this
    service reads perfectly healthy from the outside. Server and client ship
    separately; the version is the client's to choose.
    """
    with fast_app().websocket_connect("/ws/presence") as ws:
        ready = hello(ws, protocol=1)
    assert ready["t"] == "ready"
    assert ready["protocol"] == 1


def test_a_v2_hello_is_answered_with_two():
    with fast_app().websocket_connect("/ws/presence") as ws:
        ready = hello(ws, protocol=2)
    assert ready["protocol"] == 2


def test_the_server_speaks_both_versions_and_says_so_on_health():
    body = fast_app().get("/health").json()
    assert body["protocols"] == list(SUPPORTED_PROTOCOLS)
    assert 1 in SUPPORTED_PROTOCOLS and PROTOCOL_VERSION in SUPPORTED_PROTOCOLS


def test_a_version_the_server_does_not_speak_is_refused():
    with fast_app().websocket_connect("/ws/presence") as ws:
        ws.send_json(
            {"t": "hello", "token": mint(), "client": "web", "protocol": 99}
        )
        error = ws.receive_json()
    assert error["t"] == "error" and error["code"] == ERR_MALFORMED
    assert "protocol" in error["message"]


def test_a_v1_session_is_refused_the_ear_by_name_and_stays_open():
    """Refused, not ignored. A silently dropped listen_start looks to the page
    like a microphone that does not work, with nothing anywhere saying why.

    The ping behind it is load bearing for the TEST, not for the protocol.
    Written without it, this asserted on a bare ``receive_json`` and a broken
    gate made the socket answer nothing at all, so the test hung forever
    instead of failing. Measured by deleting the gate and watching it block.
    A hang in CI reads as an infrastructure problem and gets re-run; a
    failure reads as the bug it is. The pong is a frame that must arrive
    either way, so whichever comes first decides it.
    """
    with fast_app().websocket_connect("/ws/presence") as ws:
        hello(ws, protocol=1)
        ws.send_json(
            {"t": "listen_start", "turn_id": "t1", "codec": "pcm_s16le", "rate": 16000}
        )
        ws.send_json({"t": "ping", "at_ms": 1})
        answer = ws.receive_json()
        assert answer["t"] != "pong", (
            "a v1 session accepted listen_start: the protocol gate is gone, and "
            "the only reason nothing broke is that nothing sent audio yet"
        )
        assert answer["t"] == "error"
        assert answer["code"] == ERR_PROTOCOL_TOO_OLD
        assert "listen_start" in answer["message"] and "2" in answer["message"]
        assert ws.receive_json()["t"] == "pong"

        # Still a working socket: typing has not stopped working.
        ws.send_json({"t": "say", "turn_id": "t2", "text": "hello"})
        assert any(m["t"] == "token" for m in drain_to_listening(ws))


# ---------------------------------------------------------------------------
# A clip becomes a turn


def test_a_clip_comes_back_as_a_transcript_then_a_turn():
    with fast_app().websocket_connect("/ws/presence") as ws:
        hello(ws)
        speak(ws, "t1", CLIP)
        messages = drain_to_listening(ws)

    transcripts = [m for m in messages if m["t"] == "transcript"]
    assert len(transcripts) == 1, messages
    assert transcripts[0]["text"] == SPOKEN
    assert transcripts[0]["turn_id"] == "t1"
    assert transcripts[0]["provider"] == "mock"
    # MockHearing reports no confidence, and None is carried rather than
    # rounded to a number that would read as certainty.
    assert transcripts[0]["confidence"] is None
    assert any(m["t"] == "token" for m in messages)


def test_a_reported_confidence_is_carried_as_a_number():
    app = fast_app(hearing=MockHearing([SPOKEN], confidence=0.62))
    with app.websocket_connect("/ws/presence") as ws:
        hello(ws)
        speak(ws, "t1", CLIP)
        messages = drain_to_listening(ws)
    transcript = next(m for m in messages if m["t"] == "transcript")
    assert transcript["confidence"] == pytest.approx(0.62)


def test_speaking_a_turn_and_typing_it_produce_the_same_turn():
    """The behavioural half of "the ear adds no new surface"."""
    with fast_app().websocket_connect("/ws/presence") as ws:
        hello(ws)
        ws.send_json({"t": "say", "turn_id": "typed", "text": SPOKEN})
        typed = [m for m in drain_to_listening(ws) if m["t"] not in ("state", "metrics")]

    with fast_app().websocket_connect("/ws/presence") as ws:
        hello(ws)
        speak(ws, "spoken", CLIP)
        spoken = [
            m
            for m in drain_to_listening(ws)
            if m["t"] not in ("state", "metrics", "transcript")
        ]

    def shape(messages):
        return [(m["t"], m.get("text")) for m in messages if m["t"] == "token"]

    assert shape(typed) == shape(spoken)
    assert shape(typed), "the comparison passed because both sides were empty"


def test_the_clip_reaches_the_transcriber_whole():
    ear = MockHearing([SPOKEN])
    app = fast_app(hearing=ear)
    with app.websocket_connect("/ws/presence") as ws:
        hello(ws)
        ws.send_json(
            {"t": "listen_start", "turn_id": "t1", "codec": "pcm_s16le", "rate": 16000}
        )
        for seq, part in enumerate((b"aaaa", b"bbbb", b"cccc")):
            ws.send_json(
                {
                    "t": "listen_chunk",
                    "turn_id": "t1",
                    "seq": seq,
                    "b64": base64.b64encode(part).decode(),
                }
            )
        ws.send_json({"t": "listen_end", "turn_id": "t1"})
        drain_to_listening(ws)
    assert ear.heard == [b"aaaabbbbcccc"]


# ---------------------------------------------------------------------------
# What goes wrong stays one turn


def test_a_chunk_with_no_start_behind_it_is_refused_and_the_socket_lives():
    with fast_app().websocket_connect("/ws/presence") as ws:
        hello(ws)
        ws.send_json(
            {"t": "listen_chunk", "turn_id": "t1", "seq": 0, "b64": base64.b64encode(CLIP).decode()}
        )
        error = ws.receive_json()
        assert error["t"] == "error" and error["code"] == ERR_MALFORMED

        speak(ws, "t2", CLIP)
        assert any(m["t"] == "transcript" for m in drain_to_listening(ws))


def test_a_chunk_for_another_turn_is_refused():
    with fast_app().websocket_connect("/ws/presence") as ws:
        hello(ws)
        ws.send_json(
            {"t": "listen_start", "turn_id": "t1", "codec": "pcm_s16le", "rate": 16000}
        )
        ws.send_json(
            {"t": "listen_chunk", "turn_id": "other", "seq": 0, "b64": base64.b64encode(CLIP).decode()}
        )
        error = ws.receive_json()
    assert error["code"] == ERR_MALFORMED and "other" in error["message"]


def test_bad_base64_is_refused_at_the_parser():
    with fast_app().websocket_connect("/ws/presence") as ws:
        hello(ws)
        ws.send_json(
            {"t": "listen_start", "turn_id": "t1", "codec": "pcm_s16le", "rate": 16000}
        )
        ws.send_json({"t": "listen_chunk", "turn_id": "t1", "seq": 0, "b64": "not base64!!"})
        error = ws.receive_json()
    assert error["code"] == ERR_MALFORMED and "base64" in error["message"]


def test_a_chunk_larger_than_one_message_is_refused_before_the_clip_cap():
    """The two ceilings interact, and the message one bites first.

    ``MAX_MESSAGE_CHARS`` is 64,000, so a chunk can carry at most about
    48,000 bytes once base64 has grown it by a third. Found by writing the
    clip cap test with 60,000 byte chunks and getting 4400 instead of 4503:
    the frame never reached the clip at all. Worth its own test, because a
    client sizing its chunks off ``MAX_CLIP_BYTES`` alone would see every
    upload refused as malformed and have nothing pointing at why.
    """
    with fast_app().websocket_connect("/ws/presence") as ws:
        hello(ws)
        ws.send_json(
            {"t": "listen_start", "turn_id": "t1", "codec": "pcm_s16le", "rate": 16000}
        )
        ws.send_json(
            {
                "t": "listen_chunk",
                "turn_id": "t1",
                "seq": 0,
                "b64": base64.b64encode(b"\x00" * 60_000).decode(),
            }
        )
        error = ws.receive_json()
    assert error["code"] == ERR_MALFORMED
    assert str(MAX_MESSAGE_CHARS) in error["message"]


def test_an_oversized_clip_is_dropped_whole_and_never_transcribed():
    """Half an utterance transcribes to a fluent sentence that was not said.

    Nothing downstream can tell that apart from a good transcript, so the
    partial clip is dropped rather than sent.
    """
    ear = MockHearing([SPOKEN])
    app = fast_app(hearing=ear)
    # Under MAX_MESSAGE_CHARS once base64 grows it, so the clip cap is the one
    # under test rather than the frame cap above.
    chunk = b"\x00" * 40_000
    assert len(base64.b64encode(chunk)) < MAX_MESSAGE_CHARS
    sends = MAX_CLIP_BYTES // len(chunk) + 1
    assert sends * len(chunk) > MAX_CLIP_BYTES and sends <= MAX_CLIP_CHUNKS

    with app.websocket_connect("/ws/presence") as ws:
        hello(ws)
        ws.send_json(
            {"t": "listen_start", "turn_id": "t1", "codec": "pcm_s16le", "rate": 16000}
        )
        payload = base64.b64encode(chunk).decode()
        for seq in range(sends):
            ws.send_json({"t": "listen_chunk", "turn_id": "t1", "seq": seq, "b64": payload})
        error = ws.receive_json()
        assert error["code"] == ERR_CLIP_TOO_LARGE, error

        # The clip was reset, so the end of it finds nothing open.
        ws.send_json({"t": "listen_end", "turn_id": "t1"})
        assert ws.receive_json()["code"] == ERR_MALFORMED
    assert ear.heard == [], "a clip that breached the cap was transcribed anyway"


def test_a_repeated_listen_end_does_not_transcribe_the_clip_twice():
    """Found by mutation, not by design: deleting ``clip.reset()`` before the
    vendor call left every other test green.

    A client that does not hear back, or that retries after an error, sends
    ``listen_end`` again. Without the reset the bytes are still sitting there,
    so the same audio goes to the vendor a second time: one utterance, two
    bills, and two turns from one thing the user said.
    """
    ear = MockHearing([SPOKEN])
    app = fast_app(hearing=ear)
    with app.websocket_connect("/ws/presence") as ws:
        hello(ws)
        speak(ws, "t1", CLIP)
        drain_to_listening(ws)
        assert len(ear.heard) == 1

        ws.send_json({"t": "listen_end", "turn_id": "t1"})
        error = ws.receive_json()
        assert error["t"] == "error" and error["code"] == ERR_MALFORMED
    assert len(ear.heard) == 1, "the same clip was transcribed and billed twice"


def test_a_transcriber_that_refuses_fails_the_turn_and_not_the_socket():
    class Refusing:
        name = "refusing"

        async def transcribe(self, audio, *, codec, rate):
            raise HearingFailed("the transcriber refused the clip")

    with fast_app(hearing=Refusing()).websocket_connect("/ws/presence") as ws:
        hello(ws)
        speak(ws, "t1", CLIP)
        error = ws.receive_json()
        assert error["t"] == "error" and error["code"] == ERR_HEARING_FAILED

        ws.send_json({"t": "say", "turn_id": "t2", "text": "still here"})
        assert any(m["t"] == "token" for m in drain_to_listening(ws))


def test_an_unexpected_exception_also_stays_one_turn():
    """A vendor client raising something nobody predicted must not take the
    socket with it. The blanket except is deliberate and this is its test."""

    class Exploding:
        name = "exploding"

        async def transcribe(self, audio, *, codec, rate):
            raise ZeroDivisionError("something nobody predicted")

    with fast_app(hearing=Exploding()).websocket_connect("/ws/presence") as ws:
        hello(ws)
        speak(ws, "t1", CLIP)
        error = ws.receive_json()
        assert error["code"] == ERR_HEARING_FAILED

        ws.send_json({"t": "say", "turn_id": "t2", "text": "still here"})
        assert any(m["t"] == "token" for m in drain_to_listening(ws))


# ---------------------------------------------------------------------------
# The structural half


def test_the_ear_starts_a_turn_the_same_way_typing_does():
    """Reads ``_handle_listen``'s AST rather than trusting the behaviour above.

    A future edit could reach some other entry point on the session and the
    end to end tests would still pass, because the reply would still arrive.
    This pins the door the transcript walks through.
    """
    tree = ast.parse(inspect.getsource(_handle_listen))
    called = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "begin_turn" in called, "the ear stopped starting turns the normal way"

    allowed = {
        "begin_turn",
        "emit",
        "start",
        "owns",
        "append",
        "finish",
        "reset",
        "transcribe",
        "get",
        "exception",
    }
    trespass = called - allowed
    assert not trespass, (
        f"the hearing path now calls {sorted(trespass)}. A transcript enters "
        "the session through begin_turn and nothing else, so speaking a turn "
        "can never reach further than typing it."
    )


def test_a_clip_in_progress_checks_the_cap_before_it_keeps_the_bytes():
    clip = ClipInProgress()
    clip.start("t1", "pcm_s16le", 16000)
    with pytest.raises(ClipTooLarge):
        clip.append(b"x" * 10, max_bytes=4, max_chunks=8)
    assert clip.total_bytes == 0, "the breaching chunk was kept anyway"
    assert clip.finish() == b""


def test_a_clip_in_progress_caps_the_chunk_count_too():
    clip = ClipInProgress()
    clip.start("t1", "pcm_s16le", 16000)
    for _ in range(3):
        clip.append(b"x", max_bytes=1024, max_chunks=3)
    with pytest.raises(ClipTooLarge):
        clip.append(b"x", max_bytes=1024, max_chunks=3)
    assert MAX_CLIP_CHUNKS > 0


# ---------------------------------------------------------------------------
# Containers


def test_raw_pcm_is_wrapped_in_a_wav_the_stdlib_can_read():
    """Read back with ``wave`` rather than asserted against my own header.

    A transcription endpoint takes a file. Headerless samples make the vendor
    guess the rate, and a wrong guess sounds like speech at the wrong speed,
    which transcribes to confident nonsense instead of to an error.
    """
    pcm = b"\x01\x02" * 1600
    blob = wav_from_pcm(pcm, 16000)
    with wave.open(io.BytesIO(blob)) as handle:
        assert handle.getnchannels() == 1
        assert handle.getsampwidth() == 2
        assert handle.getframerate() == 16000
        assert handle.readframes(handle.getnframes()) == pcm


def test_the_upload_shape_follows_the_declared_codec():
    name, payload, content_type = upload_for(b"\x00\x00" * 10, "pcm_s16le", 16000)
    assert name.endswith(".wav") and content_type == "audio/wav"
    assert payload.startswith(b"RIFF")

    name, payload, content_type = upload_for(b"webmbytes", "webm_opus", 0)
    assert name.endswith(".webm") and content_type == "audio/webm"
    assert payload == b"webmbytes", "a container format was re-wrapped"

    with pytest.raises(HearingFailed):
        upload_for(b"x", "mp3", 0)


# ---------------------------------------------------------------------------
# The vendor adapter


def stt_app(handler) -> ElevenLabsHearing:
    return ElevenLabsHearing(FAKE_KEY, transport=httpx.MockTransport(handler))


MEASURED_BODY = {
    "text": "Go to my Google Drive",
    "language_code": "eng",
    "language_probability": 1.0,
    "words": [{"text": "Go", "logprob": -0.000433}],
}


@pytest.mark.asyncio
async def test_the_measured_response_shape_parses():
    """The shape is not guessed. Execution 296 on 2026-09-16 drove a real
    voice note through this vendor on the live account and returned exactly
    these keys."""
    seen: Dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["key"] = request.headers.get("xi-api-key")
        seen["body"] = request.content
        return httpx.Response(200, json=MEASURED_BODY)

    heard = await stt_app(handler).transcribe(b"\x00\x00" * 10, codec="pcm_s16le", rate=16000)
    assert isinstance(heard, HeardClip)
    assert heard.text == "Go to my Google Drive"
    assert heard.confidence == pytest.approx(1.0)
    assert heard.language == "eng"
    assert heard.provider == "elevenlabs"

    assert seen["url"] == ELEVENLABS_STT_URL
    assert seen["key"] == FAKE_KEY
    assert b"scribe_v1" in seen["body"]
    assert b"RIFF" in seen["body"], "raw pcm went up without a container"


@pytest.mark.asyncio
async def test_a_refusal_never_forwards_the_vendor_body():
    """Measured on the Cartesia path 2026-09-09: a 401 body echoed the
    Authorization header and the transcript straight back out through
    ``session.py``, which sends ``str(exc)`` to the socket. Here the body
    would carry the user's own voice as text."""
    leaky = json.dumps(
        {"detail": f"bad key {FAKE_KEY}", "echo": "Go to my Google Drive"}
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text=leaky)

    with pytest.raises(HearingFailed) as info:
        await stt_app(handler).transcribe(b"\x00\x00" * 10, codec="pcm_s16le", rate=16000)

    message = str(info.value)
    assert "401" in message
    assert FAKE_KEY not in message
    assert "Google Drive" not in message


@pytest.mark.asyncio
async def test_an_empty_transcript_is_a_failure_rather_than_an_empty_turn():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"text": "   ", "language_probability": 0.9})

    with pytest.raises(HearingFailed):
        await stt_app(handler).transcribe(b"\x00\x00" * 10, codec="pcm_s16le", rate=16000)


@pytest.mark.asyncio
async def test_a_non_json_answer_is_a_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>gateway</html>")

    with pytest.raises(HearingFailed):
        await stt_app(handler).transcribe(b"\x00\x00" * 10, codec="pcm_s16le", rate=16000)


@pytest.mark.asyncio
async def test_an_empty_clip_never_reaches_the_vendor():
    calls: List[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(200, json=MEASURED_BODY)

    with pytest.raises(HearingFailed):
        await stt_app(handler).transcribe(b"", codec="pcm_s16le", rate=16000)
    assert calls == [], "an empty clip was billed to the vendor"


def test_an_empty_key_is_refused_at_construction():
    with pytest.raises(HearingNotConfigured) as info:
        ElevenLabsHearing("")
    assert "ELEVENLABS_API_KEY" in str(info.value)


def test_every_model_the_vendor_named_is_accepted():
    """Found by mutation: dropping scribe_v2 from the allowlist broke nothing.

    The vendor named all four itself, 2026-09-17, in a 400 answering a request
    that carried a synthesis model id and no audio (ElevenLabs request_id
    32075172af16f7586c8e5186da95d44c). The list said only the first two until
    that probe ran, so `ELEVENLABS_STT_MODEL=scribe_v2` would have been
    refused at startup for a model the vendor accepts.
    """
    named_by_the_vendor = (
        "scribe_v1",
        "scribe_v1_experimental",
        "scribe_v2",
        "scribe_v2_medical",
    )
    assert set(ELEVENLABS_STT_MODELS) == set(named_by_the_vendor)
    for model in named_by_the_vendor:
        ear = ElevenLabsHearing(FAKE_KEY, model=model)
        assert ear.model == model


def test_a_synthesis_model_is_refused_at_construction():
    """The n8n node's own picker lists synthesis models, measured 2026-09-16.
    Naming one here would fail per clip instead of at startup."""
    with pytest.raises(HearingNotConfigured) as info:
        ElevenLabsHearing(FAKE_KEY, model="eleven_multilingual_v2")
    assert "scribe_v1" in str(info.value)


@pytest.mark.parametrize(
    "value",
    [None, True, False, "0.9", float("nan"), float("inf"), -0.1, 1.1, {}],
)
def test_an_unusable_confidence_reads_as_none_rather_than_zero(value):
    """0.0 on the wire says "heard, and certain it was nothing". None says the
    transcriber did not report. They are opposite claims."""
    assert _confidence_of({"language_probability": value}) is None


def test_a_usable_confidence_reads_as_itself():
    assert _confidence_of({"language_probability": 0.62}) == pytest.approx(0.62)
    assert _confidence_of({"language_probability": 0}) == 0.0
    assert _confidence_of({"language_probability": 1}) == 1.0


# ---------------------------------------------------------------------------
# Configuration refuses rather than half works


def test_ears_set_to_the_vendor_without_a_key_refuses_by_name():
    with pytest.raises(PresenceConfigError) as info:
        PresenceSettings(
            SECRET_KEY=TEST_SECRET, ENVIRONMENT="test", PRESENCE_EARS="elevenlabs"
        ).validate({})
    assert "ELEVENLABS_API_KEY" in str(info.value)


def test_an_unknown_ear_refuses():
    with pytest.raises(PresenceConfigError) as info:
        PresenceSettings(
            SECRET_KEY=TEST_SECRET, ENVIRONMENT="test", PRESENCE_EARS="whisper"
        ).validate({})
    assert "PRESENCE_EARS" in str(info.value)


def test_build_hearing_refuses_the_same_way_validate_does():
    with pytest.raises(HearingNotConfigured):
        build_hearing(
            PresenceSettings(SECRET_KEY=TEST_SECRET, PRESENCE_EARS="elevenlabs")
        )
    with pytest.raises(HearingNotConfigured):
        build_hearing(PresenceSettings(SECRET_KEY=TEST_SECRET, PRESENCE_EARS="whisper"))


def test_the_default_ear_is_the_one_that_needs_no_key():
    """The vendor request shape has not been executed from this repository, so
    nothing may depend on it silently. See apps/presence/hearing.py."""
    assert PresenceSettings().PRESENCE_EARS == "mock"
    assert build_hearing(PresenceSettings(SECRET_KEY=TEST_SECRET)).name == "mock"

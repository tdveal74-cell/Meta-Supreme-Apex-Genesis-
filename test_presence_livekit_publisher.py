"""The LiveKit room publisher, driven against a double that cannot drift.

Tee ruled on 2026-09-16: build the publisher. Before it existed,
`send_audio_over_websocket` was `not livekit_configured` and nothing carried
the other case, so setting the three `LIVEKIT_*` variables produced audio
frames and dropped them. `/health` answered 200, the socket opened, and DEVON
went quiet with nothing in any log.

A test double for an SDK is a fiction unless something holds it to the real
thing, so `test_the_double_matches_the_real_sdk` reads the installed `livekit`
package and asserts every call this publisher makes exists with the arguments
it passes. That test skips when the SDK is absent and runs in CI, where
`requirements.txt` pins it.
"""

from __future__ import annotations

import inspect

import pytest

from apps.presence.livekit_publisher import (
    AUDIO_CHANNELS,
    QUEUE_SIZE_MS,
    TRACK_NAME,
    AudioSink,
    LiveKitPublisher,
    LiveKitPublishError,
    LiveKitUnavailable,
    RecordingSink,
    load_rtc,
)
from apps.presence.livekit_token import decode_livekit_token
from apps.presence.protocol import AUDIO_RATE

URL = "wss://example.livekit.cloud"
KEY = "APIkey"
SECRET = "livekit-secret-0123456789abcdef0123456789abcdef"
ROOM = "session-abc"
IDENTITY = "devon-session-abc"


# ---------------------------------------------------------------------------
# The double. Shapes copied from the installed SDK, and pinned to it below.
# ---------------------------------------------------------------------------

class FakeAudioFrame:
    def __init__(self, data, sample_rate, num_channels, samples_per_channel, *, userdata=None):
        self.data = data
        self.sample_rate = sample_rate
        self.num_channels = num_channels
        self.samples_per_channel = samples_per_channel


class FakeAudioSource:
    def __init__(self, sample_rate, num_channels, queue_size_ms=1000, loop=None):
        self.sample_rate = sample_rate
        self.num_channels = num_channels
        self.queue_size_ms = queue_size_ms
        self.captured: list[FakeAudioFrame] = []
        self.closed = False

    async def capture_frame(self, frame):
        if self.closed:
            raise AssertionError("captured into a closed source")
        self.captured.append(frame)

    async def aclose(self):
        self.closed = True


class FakeLocalAudioTrack:
    def __init__(self, name, source):
        self.name = name
        self.source = source

    @staticmethod
    def create_audio_track(name, source):
        return FakeLocalAudioTrack(name, source)


class FakeTrackPublishOptions:
    def __init__(self):
        self.source = None


class FakeTrackSource:
    SOURCE_MICROPHONE = 2


class FakeLocalParticipant:
    def __init__(self):
        self.published: list[tuple] = []

    async def publish_track(self, track, options):
        self.published.append((track, options))
        return object()


class FakeRoom:
    def __init__(self, loop=None):
        self.local_participant = FakeLocalParticipant()
        self.connected_to: tuple | None = None
        self.disconnected = False

    async def connect(self, url, token, options=None):
        self.connected_to = (url, token)

    async def disconnect(self, reason=1):
        self.disconnected = True


class FakeRTC:
    """Stands in for `livekit.rtc`, remembering the room it built."""

    AudioFrame = FakeAudioFrame
    AudioSource = FakeAudioSource
    LocalAudioTrack = FakeLocalAudioTrack
    TrackPublishOptions = FakeTrackPublishOptions
    TrackSource = FakeTrackSource

    def __init__(self):
        self.rooms: list[FakeRoom] = []

    def Room(self, loop=None):  # noqa: N802 - mirrors the SDK's class name
        room = FakeRoom(loop)
        self.rooms.append(room)
        return room


def _publisher(rtc: FakeRTC) -> LiveKitPublisher:
    return LiveKitPublisher(
        url=URL, api_key=KEY, api_secret=SECRET, room=ROOM, identity=IDENTITY, rtc=rtc
    )


# ---------------------------------------------------------------------------
# Connecting and publishing the track
# ---------------------------------------------------------------------------

async def test_start_connects_and_publishes_a_microphone_track():
    rtc = FakeRTC()
    pub = _publisher(rtc)
    await pub.start()

    room = rtc.rooms[0]
    url, token = room.connected_to
    assert url == URL

    track, options = room.local_participant.published[0]
    assert track.name == TRACK_NAME
    assert options.source == FakeTrackSource.SOURCE_MICROPHONE
    assert track.source.sample_rate == AUDIO_RATE
    assert track.source.num_channels == AUDIO_CHANNELS
    assert track.source.queue_size_ms == QUEUE_SIZE_MS


async def test_the_token_is_publish_only_and_for_this_room_and_identity():
    """DEVON speaks into the room and has no reason to receive from it.

    A token that cannot subscribe is a smaller thing to leak, and the identity
    must never be the user's: `/livekit/token` mints with `sub`, so a publisher
    sharing it would collide with the human it is talking to.
    """
    rtc = FakeRTC()
    await _publisher(rtc).start()
    _, token = rtc.rooms[0].connected_to

    claims = decode_livekit_token(token, KEY, SECRET)
    assert claims["sub"] == IDENTITY
    assert claims["video"]["room"] == ROOM
    assert claims["video"]["canPublish"] is True
    assert claims["video"]["canSubscribe"] is False


async def test_start_is_idempotent_and_does_not_join_twice():
    rtc = FakeRTC()
    pub = _publisher(rtc)
    await pub.start()
    await pub.start()
    assert len(rtc.rooms) == 1


# ---------------------------------------------------------------------------
# The frame itself
# ---------------------------------------------------------------------------

async def test_a_chunk_becomes_one_frame_with_the_right_sample_count():
    rtc = FakeRTC()
    pub = _publisher(rtc)
    await pub.start()

    pcm = bytes(320 * 2)  # 320 samples of s16le mono, 20 ms at 16 kHz
    await pub.publish(pcm, at_ms=0.0)

    frame = rtc.rooms[0].local_participant.published[0][0].source.captured[0]
    assert frame.sample_rate == AUDIO_RATE
    assert frame.num_channels == AUDIO_CHANNELS
    assert frame.samples_per_channel == 320
    assert frame.data == pcm
    assert pub.frames_published == 1
    assert pub.bytes_published == len(pcm)


async def test_an_empty_chunk_is_a_no_op_rather_than_an_error():
    rtc = FakeRTC()
    pub = _publisher(rtc)
    await pub.start()
    await pub.publish(b"", at_ms=0.0)
    assert pub.frames_published == 0


async def test_half_a_sample_is_refused_rather_than_truncated():
    """`pcm_s16le` is two bytes a sample. An odd buffer means upstream is wrong.

    Truncating would hide a broken producer, which is the same class of quiet
    wrongness this whole module was written to end.
    """
    rtc = FakeRTC()
    pub = _publisher(rtc)
    await pub.start()
    with pytest.raises(LiveKitPublishError, match="whole number"):
        await pub.publish(b"\x00\x01\x02", at_ms=0.0)


async def test_publishing_before_start_is_loud():
    """A sink that accepts frames it never sends is the bug, not the fallback."""
    pub = _publisher(FakeRTC())
    with pytest.raises(LiveKitPublishError, match="before start"):
        await pub.publish(bytes(64), at_ms=0.0)


async def test_publishing_after_close_is_loud():
    rtc = FakeRTC()
    pub = _publisher(rtc)
    await pub.start()
    await pub.aclose()
    with pytest.raises(LiveKitPublishError, match="after close"):
        await pub.publish(bytes(64), at_ms=0.0)


# ---------------------------------------------------------------------------
# Leaving
# ---------------------------------------------------------------------------

async def test_close_releases_the_source_and_leaves_the_room():
    rtc = FakeRTC()
    pub = _publisher(rtc)
    await pub.start()
    source = rtc.rooms[0].local_participant.published[0][0].source
    await pub.aclose()
    assert source.closed is True
    assert rtc.rooms[0].disconnected is True


async def test_close_twice_is_safe():
    rtc = FakeRTC()
    pub = _publisher(rtc)
    await pub.start()
    await pub.aclose()
    await pub.aclose()


async def test_a_closed_publisher_refuses_to_restart():
    rtc = FakeRTC()
    pub = _publisher(rtc)
    await pub.start()
    await pub.aclose()
    with pytest.raises(LiveKitPublishError, match="closed"):
        await pub.start()


# ---------------------------------------------------------------------------
# Construction refuses what it cannot honour
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "kwargs, match",
    [
        ({"url": ""}, "LIVEKIT_URL"),
        ({"room": "  "}, "room name"),
        ({"identity": ""}, "identity"),
    ],
)
def test_construction_refuses_a_missing_essential(kwargs, match):
    base = dict(url=URL, api_key=KEY, api_secret=SECRET, room=ROOM, identity=IDENTITY)
    base.update(kwargs)
    with pytest.raises(ValueError, match=match):
        LiveKitPublisher(**base)


# ---------------------------------------------------------------------------
# The double is held to the real SDK
# ---------------------------------------------------------------------------

def test_the_double_matches_the_real_sdk():
    """Every call the publisher makes must exist on the installed `livekit`.

    Without this the double is a story about an API rather than a stand-in for
    one, and a green suite would say nothing about whether a real room would
    accept a single frame. Skips when the SDK is absent so a developer without
    it can still run the suite; CI has it pinned.
    """
    rtc = pytest.importorskip("livekit.rtc", reason="livekit SDK not installed here")

    source_params = inspect.signature(rtc.AudioSource.__init__).parameters
    for name in ("sample_rate", "num_channels", "queue_size_ms"):
        assert name in source_params, f"AudioSource lost {name}"

    frame_params = inspect.signature(rtc.AudioFrame.__init__).parameters
    for name in ("data", "sample_rate", "num_channels", "samples_per_channel"):
        assert name in frame_params, f"AudioFrame lost {name}"

    assert inspect.iscoroutinefunction(rtc.AudioSource.capture_frame)
    assert inspect.iscoroutinefunction(rtc.AudioSource.aclose)
    assert inspect.iscoroutinefunction(rtc.Room.connect)
    assert inspect.iscoroutinefunction(rtc.Room.disconnect)
    assert inspect.iscoroutinefunction(rtc.LocalParticipant.publish_track)

    assert hasattr(rtc.LocalAudioTrack, "create_audio_track")
    assert rtc.TrackSource.SOURCE_MICROPHONE == FakeTrackSource.SOURCE_MICROPHONE
    options = rtc.TrackPublishOptions()
    options.source = rtc.TrackSource.SOURCE_MICROPHONE
    assert options.source == rtc.TrackSource.SOURCE_MICROPHONE


def test_load_rtc_names_the_remedy_when_the_sdk_is_missing(monkeypatch):
    """The refusal has to say what to do, because the reader is mid outage."""
    import builtins

    real_import = builtins.__import__

    def refuse(name, *args, **kwargs):
        if name == "livekit" or name.startswith("livekit."):
            raise ImportError("No module named 'livekit'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", refuse)
    with pytest.raises(LiveKitUnavailable) as exc:
        load_rtc()
    message = str(exc.value)
    assert "LIVEKIT_URL" in message
    assert "requirements.txt" in message
    assert "unset" in message


# ---------------------------------------------------------------------------
# The test sink
# ---------------------------------------------------------------------------

async def test_the_recording_sink_records_rather_than_discards():
    """Deliberately not a null sink: accept-and-discard IS the bug."""
    sink = RecordingSink()
    assert isinstance(sink, AudioSink)
    await sink.start()
    await sink.publish(b"\x01\x02", 0.0)
    await sink.publish(b"\x03\x04", 20.0)
    assert sink.chunks == [(b"\x01\x02", 0.0), (b"\x03\x04", 20.0)]
    assert sink.total_bytes == 4
    await sink.aclose()
    with pytest.raises(LiveKitPublishError):
        await sink.publish(b"\x05\x06", 40.0)


async def test_the_recording_sink_refuses_a_publish_before_start():
    sink = RecordingSink()
    with pytest.raises(LiveKitPublishError, match="before start"):
        await sink.publish(b"\x01\x02", 0.0)

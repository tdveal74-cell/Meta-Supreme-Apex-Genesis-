"""DEVON's audio, published into a LiveKit room instead of onto the socket.

WHY THIS EXISTS

Until 2026-09-16 this service could mint a LiveKit join token and could not
send a single audio frame into a room. `apps/presence/__init__.py` said so
plainly and `main.py` encoded it: `send_audio_over_websocket` is
`not livekit_configured`, so audio went over the WebSocket only while LiveKit
was unconfigured, and once it WAS configured the frames were produced and
dropped on the floor.

That made the three `LIVEKIT_*` variables a trap rather than a setting. Filling
them in reads like completing a configuration and was in fact how DEVON went
silent: `/health` still answered 200, the socket still opened, the page still
rendered, and nobody got told. Worse, `POST /livekit/token` returned a 503
whose text instructed the reader to set exactly those three variables.

Tee ruled on 2026-09-16: build the publisher. This is it.

THE SHAPE

`PresenceSession` does not know LiveKit exists. It takes an `AudioSink`, and
the socket path and the room path are two answers to the same question. That
keeps the session testable without a room and keeps this module the only place
that imports the SDK.

The room is the session id. That convention is not invented here: `main.py`
already registers `runtime.sessions[session_id] = user_id` and
`POST /livekit/token` refuses to mint for a room whose registered owner is not
the caller. So the browser and this publisher meet in a room named for the
session, and the token endpoint is what stops a signed in user minting their
way into somebody else's.

The publisher's own identity is deliberately NOT the user's. `/livekit/token`
mints with `identity = sub`, the DEVON user id; a publisher joining under that
same identity would collide with the human it is speaking to.

WHAT IT REFUSES

A publish before `start()`, because a sink that quietly accepts frames it never
sends is the exact failure this module was written to end. An odd length PCM
buffer, because `pcm_s16le` is two bytes a sample and half a sample means the
producer upstream is broken; truncating it would hide that. And a missing SDK
when LiveKit is configured, which raises `LiveKitUnavailable` naming the fix
rather than degrading to silence.

PACING

`AudioSource.capture_frame` is a coroutine that waits for room in the source's
own queue, so publishing paces itself at real time. That is correct for a live
room and it is a real difference from the socket path, where a chunk leaves the
instant it exists. It does not stall the face: `PresenceSession` runs its
producer as a separate task from the frame drain loop, so awaiting here holds
audio and never holds blendshapes.
"""

from __future__ import annotations

from typing import Any, Optional, Protocol, runtime_checkable

from apps.presence.livekit_token import mint_livekit_token
from apps.presence.protocol import AUDIO_RATE

#: The wire format `speech.py` produces and `protocol.audio_message` names:
#: `pcm_s16le`, mono, at `AUDIO_RATE`. Two bytes per sample, one channel.
AUDIO_CHANNELS = 1
BYTES_PER_SAMPLE = 2

#: The track's name inside the room. Visible to every participant, so it says
#: who is speaking rather than what the code calls it.
TRACK_NAME = "devon"

#: How much audio the SDK will hold before `capture_frame` waits. One second
#: is the SDK's own default and is left explicit because it IS the pacing.
QUEUE_SIZE_MS = 1000


class LiveKitUnavailable(RuntimeError):
    """LiveKit is configured and the SDK that publishes into it is missing.

    Raised at start up rather than at the first frame. A service that accepts
    a configuration it cannot honour and then goes quiet is the bug this whole
    module exists to remove.
    """


class LiveKitPublishError(RuntimeError):
    """A frame could not be published, and that is not allowed to be silent."""


def load_rtc() -> Any:
    """Import `livekit.rtc`, or raise naming the remedy.

    Imported lazily and in one place. Every other module in this service, and
    the test suite, loads without the SDK present; only a deployment that has
    actually set `LIVEKIT_*` needs it.
    """
    try:
        from livekit import rtc  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - exercised by a stub in tests
        raise LiveKitUnavailable(
            "LIVEKIT_URL, LIVEKIT_API_KEY and LIVEKIT_API_SECRET are set, so this "
            "service is expected to publish audio into a LiveKit room, but the "
            "`livekit` package is not importable: "
            f"{exc}. Install it (it is pinned in requirements.txt) or unset the "
            "three LIVEKIT_ variables, which returns audio to the WebSocket."
        ) from exc
    return rtc


@runtime_checkable
class AudioSink(Protocol):
    """Where a turn's audio goes. The socket is one; a LiveKit room is another."""

    async def start(self) -> None: ...

    async def publish(self, pcm: bytes, at_ms: float) -> None: ...

    async def aclose(self) -> None: ...


class RecordingSink:
    """An `AudioSink` that keeps what it was given. For tests, and only tests.

    Deliberately not a null sink. A sink that accepts and discards is precisely
    the shape of the bug being fixed, so the test double remembers instead.
    """

    def __init__(self) -> None:
        self.chunks: list[tuple[bytes, float]] = []
        self.started = False
        self.closed = False

    async def start(self) -> None:
        self.started = True

    async def publish(self, pcm: bytes, at_ms: float) -> None:
        if self.closed:
            raise LiveKitPublishError("published after close")
        if not self.started:
            raise LiveKitPublishError("published before start")
        self.chunks.append((pcm, at_ms))

    async def aclose(self) -> None:
        self.closed = True

    @property
    def total_bytes(self) -> int:
        return sum(len(pcm) for pcm, _ in self.chunks)


class LiveKitPublisher:
    """One room, one outbound audio track, for the life of one session."""

    def __init__(
        self,
        *,
        url: str,
        api_key: str,
        api_secret: str,
        room: str,
        identity: str,
        sample_rate: int = AUDIO_RATE,
        rtc: Optional[Any] = None,
    ) -> None:
        if not url or not url.strip():
            raise ValueError("LIVEKIT_URL is required to publish into a room")
        if not room or not room.strip():
            raise ValueError("a room name is required; presence uses the session id")
        if not identity or not identity.strip():
            raise ValueError("an identity is required, and it must not be the user's")
        self.url = url
        self.api_key = api_key
        self.api_secret = api_secret
        self.room_name = room
        self.identity = identity
        self.sample_rate = int(sample_rate)
        #: Injectable so a test drives the real call sequence against a double.
        #: Left None in production, where `start` loads the real SDK.
        self._rtc = rtc
        self._room: Any = None
        self._source: Any = None
        self._publication: Any = None
        self._started = False
        self._closed = False
        self.frames_published = 0
        self.bytes_published = 0

    async def start(self) -> None:
        """Connect, create the track, publish it. Idempotent."""
        if self._started:
            return
        if self._closed:
            raise LiveKitPublishError("this publisher is closed; build a new one")
        rtc = self._rtc if self._rtc is not None else load_rtc()

        token = mint_livekit_token(
            self.api_key,
            self.api_secret,
            identity=self.identity,
            room=self.room_name,
            name=TRACK_NAME,
            # DEVON speaks into the room. It has no reason to receive from it,
            # and a token that cannot subscribe is a smaller token to leak.
            can_publish=True,
            can_subscribe=False,
        )

        room = rtc.Room()
        await room.connect(self.url, token)

        source = rtc.AudioSource(self.sample_rate, AUDIO_CHANNELS, QUEUE_SIZE_MS)
        track = rtc.LocalAudioTrack.create_audio_track(TRACK_NAME, source)
        options = rtc.TrackPublishOptions()
        options.source = rtc.TrackSource.SOURCE_MICROPHONE
        publication = await room.local_participant.publish_track(track, options)

        self._room, self._source, self._publication = room, source, publication
        self._started = True

    async def publish(self, pcm: bytes, at_ms: float) -> None:
        """Send one PCM chunk into the room as an audio frame.

        `at_ms` is the chunk's place on the turn's timeline. LiveKit carries its
        own clock, so it is not sent; it is accepted so this satisfies the same
        `AudioSink` protocol as the socket path, whose messages do carry it.
        """
        if self._closed:
            raise LiveKitPublishError("published after close")
        if not self._started:
            raise LiveKitPublishError(
                "publish() before start(): the room is not connected and this "
                "frame would be lost. Call start() when the session opens."
            )
        if not pcm:
            return
        if len(pcm) % BYTES_PER_SAMPLE:
            raise LiveKitPublishError(
                f"PCM buffer is {len(pcm)} bytes, which is not a whole number of "
                f"{BYTES_PER_SAMPLE} byte samples. Half a sample means the "
                "producer upstream is wrong; truncating it here would hide that."
            )

        rtc = self._rtc if self._rtc is not None else load_rtc()
        frame = rtc.AudioFrame(
            data=pcm,
            sample_rate=self.sample_rate,
            num_channels=AUDIO_CHANNELS,
            samples_per_channel=len(pcm) // BYTES_PER_SAMPLE,
        )
        await self._source.capture_frame(frame)
        self.frames_published += 1
        self.bytes_published += len(pcm)

    async def aclose(self) -> None:
        """Close the source and leave the room. Safe to call twice."""
        if self._closed:
            return
        self._closed = True
        self._started = False
        source, room = self._source, self._room
        self._source = self._room = self._publication = None
        if source is not None:
            await source.aclose()
        if room is not None:
            await room.disconnect()

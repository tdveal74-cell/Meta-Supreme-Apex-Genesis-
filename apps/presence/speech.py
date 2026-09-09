"""Speech synthesis: text in, audio and face frames out on one timeline.

A ``SpeechSynthesizer`` yields ``SpeechChunk`` objects, each either a face
frame (ARKit weights at ``at_ms`` with a priority), an audio chunk (raw
``pcm_s16le`` at 16000 Hz starting at ``at_ms``) or a state cue. The
session pushes frames into the sliding window buffer and sends audio the
moment it appears, which is what keeps audio outside the buffer.

``MockSpeech`` is deterministic and needs no network. It produces viseme
frames at 60 frames per second from the text itself: vowels open the jaw
(jawOpen 0.35 to 0.7), o and u add mouthFunnel or mouthPucker, m b p close
the lips with mouthClose and mouthPress, f v roll the lower lip, other
consonants leave the jaw slightly open, and gaps between words return to
rest. A blink runs every three seconds as a separate priority 1 frame so
the buffer can shed it before it sheds a mouth shape. Word rate is 150
words per minute. It emits audio too: 100 ms chunks of silence, so the
WebSocket audio path and the client's audio clock are exercised end to
end without a vendor. Pass ``emit_silence=False`` to get frames only.

``CartesiaSpeech`` streams from Cartesia's SSE text to speech endpoint
and drives the face from the audio it actually receives. See the class
docstring for what was read from the vendor and what is still unverified.
"""

from __future__ import annotations

import base64
import json
import math
import sys
from array import array
from bisect import bisect_right
from contextlib import aclosing
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional, Protocol, Sequence, Tuple

import httpx

from apps.presence.protocol import AUDIO_RATE, PRIORITY_EXPRESSION, PRIORITY_LIP_SYNC
from apps.presence.settings import CARTESIA_VOICE_RULE, PresenceSettings

CHUNK_FRAME = "frame"
CHUNK_AUDIO = "audio"
CHUNK_STATE = "state"

STATE_SPEAKING = "speaking"
STATE_DONE = "done"


class SpeechNotConfigured(RuntimeError):
    """The configured synthesiser cannot speak. The message names the gate."""


@dataclass
class SpeechChunk:
    """One unit of speech output on the audio timeline."""

    kind: str
    at_ms: float
    weights: Dict[str, float] = field(default_factory=dict)
    priority: int = PRIORITY_LIP_SYNC
    pcm: bytes = b""
    state: str = ""

    @property
    def audio_duration_ms(self) -> float:
        """Duration of the PCM payload, two bytes per sample at AUDIO_RATE."""
        return (len(self.pcm) / 2) / AUDIO_RATE * 1000.0


class SpeechSynthesizer(Protocol):
    name: str

    def synthesize(self, text: str, turn: str) -> AsyncIterator[SpeechChunk]: ...


# ---------------------------------------------------------------------------
# Mock: deterministic visemes from text
# ---------------------------------------------------------------------------

_REST: Dict[str, float] = {"jawOpen": 0.0}
_VOWELS: Dict[str, Dict[str, float]] = {
    "a": {"jawOpen": 0.7},
    "e": {"jawOpen": 0.5, "mouthSmileLeft": 0.2, "mouthSmileRight": 0.2},
    "i": {"jawOpen": 0.4, "mouthSmileLeft": 0.3, "mouthSmileRight": 0.3},
    "o": {"jawOpen": 0.55, "mouthFunnel": 0.5},
    "u": {"jawOpen": 0.35, "mouthPucker": 0.6},
}
_LIPS_CLOSED: Dict[str, float] = {
    "jawOpen": 0.0,
    "mouthClose": 0.8,
    "mouthPressLeft": 0.5,
    "mouthPressRight": 0.5,
}
_LABIODENTAL: Dict[str, float] = {"jawOpen": 0.1, "mouthRollLower": 0.6}
_CONSONANT: Dict[str, float] = {"jawOpen": 0.2}


def shape_for(char: str) -> Dict[str, float]:
    """The mouth shape for one letter. Anything unrecognised is a light consonant."""
    lower = char.lower()
    if lower == "y":
        lower = "i"
    if lower in _VOWELS:
        return _VOWELS[lower]
    if lower in ("m", "b", "p"):
        return _LIPS_CLOSED
    if lower in ("f", "v"):
        return _LABIODENTAL
    return _CONSONANT


@dataclass
class Segment:
    start_ms: float
    end_ms: float
    shape: Dict[str, float]


def _blend(before: Dict[str, float], after: Dict[str, float], amount: float) -> Dict[str, float]:
    keys = set(before) | set(after)
    out: Dict[str, float] = {}
    for key in sorted(keys):
        value = before.get(key, 0.0) * (1.0 - amount) + after.get(key, 0.0) * amount
        out[key] = round(min(1.0, max(0.0, value)), 3)
    return out


class MockSpeech:
    """Deterministic visemes and silence from text. No network, no vendor."""

    name = "mock"

    def __init__(
        self,
        *,
        fps: int = 60,
        words_per_minute: float = 150.0,
        voiced_fraction: float = 0.8,
        sentence_pause_ms: float = 200.0,
        blink_every_ms: float = 3000.0,
        blink_ms: float = 120.0,
        blink_offset_ms: float = 1500.0,
        ramp_ms: float = 40.0,
        tail_ms: float = 100.0,
        emit_silence: bool = True,
        silence_chunk_ms: float = 100.0,
    ) -> None:
        if fps <= 0 or words_per_minute <= 0:
            raise ValueError("fps and words_per_minute must be greater than zero")
        self.fps = fps
        self.words_per_minute = float(words_per_minute)
        self.voiced_fraction = min(1.0, max(0.0, voiced_fraction))
        self.sentence_pause_ms = float(sentence_pause_ms)
        self.blink_every_ms = float(blink_every_ms)
        self.blink_ms = float(blink_ms)
        self.blink_offset_ms = float(blink_offset_ms)
        self.ramp_ms = float(ramp_ms)
        self.tail_ms = float(tail_ms)
        self.emit_silence = emit_silence
        self.silence_chunk_ms = float(silence_chunk_ms)

    @property
    def frame_ms(self) -> float:
        return 1000.0 / self.fps

    @property
    def word_ms(self) -> float:
        return 60_000.0 / self.words_per_minute

    def plan(self, text: str) -> Tuple[List[Segment], float]:
        """Timeline segments for the text and its total length in ms."""
        segments: List[Segment] = []
        cursor = 0.0
        for word in text.split():
            letters = [char for char in word if char.isalpha()]
            voiced = self.word_ms * self.voiced_fraction
            if letters:
                per_letter = voiced / len(letters)
                for char in letters:
                    segments.append(Segment(cursor, cursor + per_letter, shape_for(char)))
                    cursor += per_letter
            else:
                segments.append(Segment(cursor, cursor + voiced, _REST))
                cursor += voiced
            gap = self.word_ms - voiced
            if word[-1] in ".!?":
                gap += self.sentence_pause_ms
            segments.append(Segment(cursor, cursor + gap, _REST))
            cursor += gap
        total = cursor + self.tail_ms
        segments.append(Segment(cursor, total, _REST))
        return segments, total

    def blink_weight(self, at_ms: float) -> float:
        """Triangular blink envelope, 0 outside a blink.

        Delegates to the module level `blink_weight` so a Cartesia driven face
        blinks on exactly the same envelope as this one. Two copies would drift
        and the drift would only show as one of the two faces feeling wrong.
        """
        return blink_weight(
            at_ms,
            every_ms=self.blink_every_ms,
            blink_ms=self.blink_ms,
            offset_ms=self.blink_offset_ms,
        )

    def frames(self, text: str) -> List[SpeechChunk]:
        """Every face frame for the text, in timeline order. Pure and testable."""
        segments, total = self.plan(text)
        count = int(total // self.frame_ms) + 1
        chunks: List[SpeechChunk] = []
        index = 0
        previous = _REST
        for k in range(count):
            at_ms = round(k * self.frame_ms, 3)
            while index + 1 < len(segments) and at_ms >= segments[index].end_ms:
                previous = segments[index].shape
                index += 1
            segment = segments[index]
            if self.ramp_ms > 0:
                amount = min(1.0, (at_ms - segment.start_ms) / self.ramp_ms)
            else:
                amount = 1.0
            chunks.append(
                SpeechChunk(
                    kind=CHUNK_FRAME,
                    at_ms=at_ms,
                    weights=_blend(previous, segment.shape, amount),
                    priority=PRIORITY_LIP_SYNC,
                )
            )
            blink = self.blink_weight(at_ms)
            if blink > 0:
                chunks.append(
                    SpeechChunk(
                        kind=CHUNK_FRAME,
                        at_ms=at_ms,
                        weights={"eyeBlinkLeft": blink, "eyeBlinkRight": blink},
                        priority=PRIORITY_EXPRESSION,
                    )
                )
        return chunks

    def silence_chunk(self, at_ms: float) -> SpeechChunk:
        samples = int(AUDIO_RATE * self.silence_chunk_ms / 1000.0)
        return SpeechChunk(kind=CHUNK_AUDIO, at_ms=at_ms, pcm=bytes(samples * 2))

    async def synthesize(self, text: str, turn: str) -> AsyncIterator[SpeechChunk]:
        frames = self.frames(text)
        total_ms = frames[-1].at_ms if frames else 0.0
        yield SpeechChunk(kind=CHUNK_STATE, at_ms=0.0, state=STATE_SPEAKING)
        next_audio_ms = 0.0
        for frame in frames:
            while self.emit_silence and next_audio_ms <= frame.at_ms and next_audio_ms <= total_ms:
                yield self.silence_chunk(next_audio_ms)
                next_audio_ms += self.silence_chunk_ms
            yield frame
        yield SpeechChunk(kind=CHUNK_STATE, at_ms=total_ms, state=STATE_DONE)


# ---------------------------------------------------------------------------
# Cartesia: real audio, and a face driven by that audio
# ---------------------------------------------------------------------------

#: Read from the vendor's own generated client, `cartesia==4.2.0` from PyPI,
#: on 2026-09-09, rather than from memory or from a blocked documentation page.
#: Base URL `cartesia/_client.py:130`, path `cartesia/resources/tts.py`
#: (`self._post("/tts/sse", ..., stream=True)`), headers `_client.py:236` and
#: `_client.py:244`, body `cartesia/types/tts_generate_sse_params.py`, event
#: shapes `cartesia/types/tts_sse_event.py`.
CARTESIA_TTS_URL = "https://api.cartesia.ai/tts/sse"
CARTESIA_VERSION = "2026-08-14"

#: The vendor types this as `Union[Literal[...], str]`, so an unknown name is
#: the API's business rather than this module's: refusing one here would break
#: the day Cartesia ships a model this constant has not heard of. The known set
#: is kept only so a typo can be spotted in a log line.
CARTESIA_KNOWN_MODELS = (
    "sonic-3.5",
    "sonic-3",
    "sonic-3.5-2026-05-04",
    "sonic-3-2026-01-12",
    "sonic-3-2025-10-27",
    "sonic-latest",
)
DEFAULT_CARTESIA_MODEL = "sonic-3"

#: `raw` plus `pcm_s16le` at 16000 is exactly what apps/presence/protocol.py
#: already puts on the wire (AUDIO_RATE, and the "pcm_s16le" the audio message
#: declares), so nothing resamples anywhere. All three values are in the
#: vendor's own enums: `raw_output_format_param.py`, `raw_encoding.py`.
CARTESIA_OUTPUT_FORMAT = {
    "container": "raw",
    "encoding": "pcm_s16le",
    "sample_rate": AUDIO_RATE,
}

CARTESIA_CONNECT_TIMEOUT_S = 10.0
CARTESIA_READ_TIMEOUT_S = 30.0

#: Fraction of full scale below which the mouth is shut. Room tone and the
#: tail of a breath sit here.
SPEECH_FLOOR = 0.02
#: Fraction of full scale at which the shape is fully formed. Above it the
#: envelope saturates rather than clipping the weights one by one.
SPEECH_CEILING = 0.30
#: Loudness does not map linearly onto how far a jaw travels; the exponent
#: lifts the quiet half so ordinary speech is visible rather than a mumble.
#: Calibrated against synthetic tones only. See the class docstring.
SPEECH_CURVE = 0.6

#: Used where no word is known to cover the moment. The envelope still decides
#: how far it opens, so silence still closes the mouth.
_NEUTRAL_VOICED: Dict[str, float] = {"jawOpen": 0.45}


def rms_of(pcm: bytes) -> float:
    """Root mean square of little endian signed 16 bit PCM, 0 to 32768.

    `array` is native endian, so it is byte swapped on a big endian host. The
    wire format is little endian whatever this process runs on, and a silent
    sign flip would read as a mouth that never opens.
    """
    usable = len(pcm) - (len(pcm) % 2)
    if usable <= 0:
        return 0.0
    samples = array("h")
    samples.frombytes(pcm[:usable])
    if sys.byteorder != "little":
        samples.byteswap()
    total = 0
    for sample in samples:
        total += sample * sample
    return math.sqrt(total / len(samples))


def envelope_from_rms(rms: float) -> float:
    """How open the mouth is, 0 to 1, for one slice of real audio."""
    level = rms / 32768.0
    if level <= SPEECH_FLOOR:
        return 0.0
    span = (level - SPEECH_FLOOR) / (SPEECH_CEILING - SPEECH_FLOOR)
    return round(min(1.0, span) ** SPEECH_CURVE, 3)


class WordClock:
    """Word timings as they arrive, and the mouth shape owed to a moment.

    Cartesia sends `timestamps` events carrying three parallel lists: the
    words, their start times in seconds and their end times. Events accumulate
    here because a reply arrives as several of them and a lookup has to see
    every word received so far.
    """

    def __init__(self) -> None:
        self.words: List[str] = []
        self.starts_ms: List[float] = []
        self.ends_ms: List[float] = []

    def extend(self, timestamps: Any) -> None:
        """Take one `word_timestamps` object. Anything malformed is ignored.

        A speaking avatar must not fail because a timing block came back short;
        the amplitude envelope carries the face on its own without it.
        """
        if not isinstance(timestamps, dict):
            return
        words = timestamps.get("words")
        starts = timestamps.get("start")
        ends = timestamps.get("end")
        if not isinstance(words, list) or not isinstance(starts, list) or not isinstance(ends, list):
            return
        # strict=False on purpose: three ragged lists are a malformed payload,
        # and truncating to the shortest keeps a reply speaking where raising
        # would drop the whole turn over a timing block nothing depends on.
        for word, start, end in zip(words, starts, ends, strict=False):
            if not isinstance(word, str):
                continue
            if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
                continue
            if isinstance(start, bool) or isinstance(end, bool):
                continue
            start_ms = float(start) * 1000.0
            end_ms = float(end) * 1000.0
            if not (math.isfinite(start_ms) and math.isfinite(end_ms)) or end_ms <= start_ms:
                continue
            # Out of order arrivals would break the bisect below, so a word that
            # starts before the last one already recorded is dropped rather than
            # silently corrupting every later lookup.
            if self.starts_ms and start_ms < self.starts_ms[-1]:
                continue
            self.words.append(word)
            self.starts_ms.append(start_ms)
            self.ends_ms.append(end_ms)

    def shape_at(self, at_ms: float) -> Optional[Dict[str, float]]:
        """The letter shape owed to this moment, or None if no word covers it."""
        if not self.starts_ms:
            return None
        index = bisect_right(self.starts_ms, at_ms) - 1
        if index < 0 or at_ms >= self.ends_ms[index]:
            return None
        letters = [char for char in self.words[index] if char.isalpha()]
        if not letters:
            return None
        span = self.ends_ms[index] - self.starts_ms[index]
        position = int((at_ms - self.starts_ms[index]) / span * len(letters))
        return shape_for(letters[min(position, len(letters) - 1)])


def blink_weight(
    at_ms: float, *, every_ms: float = 3000.0, blink_ms: float = 120.0, offset_ms: float = 1500.0
) -> float:
    """Triangular blink envelope, 0 outside a blink.

    Shared so a Cartesia driven face blinks exactly as the mock one does.
    ``MockSpeech.blink_weight`` delegates here rather than holding a copy.
    """
    if at_ms < offset_ms or every_ms <= 0 or blink_ms <= 0:
        return 0.0
    phase = (at_ms - offset_ms) % every_ms
    if phase >= blink_ms:
        return 0.0
    half = blink_ms / 2.0
    return round(1.0 - abs(phase - half) / half, 3)


def sse_payloads(lines: Sequence[str]) -> List[str]:
    """The `data:` payloads in a block of Server Sent Event lines.

    Written out rather than pulled from a library because httpx does not parse
    SSE and adding a dependency for twelve lines would put a new package in a
    hash pinned closure that the audit lane also has to carry. Multiple `data:`
    lines in one event are joined with a newline, which is what the SSE
    specification says and what a JSON payload split across lines needs.
    """
    payloads: List[str] = []
    current: List[str] = []
    for raw in lines:
        line = raw.rstrip("\r")
        if not line:
            if current:
                payloads.append("\n".join(current))
                current = []
            continue
        if line.startswith(":"):
            continue
        if line.startswith("data:"):
            current.append(line[5:].lstrip(" "))
    if current:
        payloads.append("\n".join(current))
    return payloads


class FrameSlicer:
    """Cuts a stream of audio chunks into frames at a fixed rate, across boundaries.

    THE BUG THIS EXISTS TO STOP, found by a fresh critic on 2026-09-09.

    The first version of this sliced each chunk independently: frame boundaries
    were computed from the start of the chunk and any tail shorter than a frame
    was discarded. That made the face's frame rate a function of the vendor's
    chunk size, which is the one thing about Cartesia this build could not
    verify, and the critic measured what that costs. Two seconds of audio
    delivered in 128, 160 or 265 sample chunks produced **zero** face frames:
    perfect audio and a completely still mouth, with nothing anywhere saying so.
    At 320 samples it produced 50 frames a second, at 480 it produced 33.

    That was the same mistake the design was built to avoid one layer up. The
    face was deliberately moved off word timings so it would not depend on an
    event ordering nobody here has observed, and then it depended on a chunk
    size nobody here has observed instead.

    So the residual carries. Samples left over at the end of a chunk are held
    and prepended to the next one, frame boundaries are absolute positions in
    the turn rather than in the chunk, and the rate is exactly `fps` for any
    chunk size the vendor cares to send. `flush` emits one final frame for a
    tail shorter than a frame, so no audio ever plays with no face over it.
    """

    def __init__(self, fps: int = 60) -> None:
        if fps <= 0:
            raise ValueError("fps must be greater than zero")
        self.fps = fps
        #: Samples held back because they do not fill a whole frame yet.
        self._held = bytearray()
        #: Absolute sample index, within the turn, of `_held[0]`.
        self._held_at = 0
        #: How many frames this turn has emitted. The next frame is this index.
        self.emitted = 0

    @property
    def samples_per_frame(self) -> float:
        """Deliberately a float. 16000 / 60 is 266.67, and truncating it to 266
        every frame runs 0.25 percent fast, which the measured case below puts at
        149.9 ms, about nine frames, one minute into a reply."""
        return AUDIO_RATE / self.fps

    def _frame_at(self, index: int) -> int:
        """Absolute sample index where frame `index` begins."""
        return int(index * self.samples_per_frame)

    def push(
        self, pcm: bytes, at_samples: int, clock: "WordClock"
    ) -> List[SpeechChunk]:
        """Every whole frame this chunk completes, in timeline order.

        `at_samples` is where this chunk sits in the turn. It is checked rather
        than trusted: a caller that skipped or repeated samples would otherwise
        put the face on a different timeline from the voice, silently.
        """
        expected = self._held_at + len(self._held) // 2
        if at_samples != expected:
            raise ValueError(
                f"audio chunk starts at sample {at_samples} and the slicer is at "
                f"{expected}; the face and the voice would be on different clocks"
            )
        self._held.extend(pcm)
        return self._cut(clock, whole_frames_only=True)

    def flush(self, clock: "WordClock") -> List[SpeechChunk]:
        """One frame for a tail shorter than a frame, so no audio goes uncovered."""
        return self._cut(clock, whole_frames_only=False)

    def _cut(self, clock: "WordClock", *, whole_frames_only: bool) -> List[SpeechChunk]:
        out: List[SpeechChunk] = []
        while True:
            low = self._frame_at(self.emitted)
            high = self._frame_at(self.emitted + 1)
            available = self._held_at + len(self._held) // 2
            if low >= available:
                break
            if high > available:
                if whole_frames_only:
                    break
                # The turn is over and this is the last partial frame. Measure
                # what there is rather than dropping it.
                high = available
            offset = (low - self._held_at) * 2
            end = (high - self._held_at) * 2
            at_ms = low / AUDIO_RATE * 1000.0
            envelope = envelope_from_rms(rms_of(bytes(self._held[offset:end])))
            shape = clock.shape_at(at_ms)
            if shape is None:
                shape = _NEUTRAL_VOICED
            out.append(
                SpeechChunk(
                    kind=CHUNK_FRAME,
                    at_ms=round(at_ms, 3),
                    weights=_blend(_REST, shape, envelope),
                    priority=PRIORITY_LIP_SYNC,
                )
            )
            blink = blink_weight(at_ms)
            if blink > 0:
                out.append(
                    SpeechChunk(
                        kind=CHUNK_FRAME,
                        at_ms=round(at_ms, 3),
                        weights={"eyeBlinkLeft": blink, "eyeBlinkRight": blink},
                        priority=PRIORITY_EXPRESSION,
                    )
                )
            self.emitted += 1
            # Everything before the next frame's start is spent.
            spent = (self._frame_at(self.emitted) - self._held_at) * 2
            if spent > 0:
                del self._held[:spent]
                self._held_at += spent // 2
        return out


class CartesiaSpeech:
    """Cartesia over SSE, with the face driven by the audio that comes back.

    WHAT WAS READ, AND FROM WHERE

    The endpoint, headers, request body and event shapes were read from the
    vendor's own generated client (`cartesia==4.2.0` from PyPI) on 2026-09-09,
    not from memory: the documentation host is unreachable from this
    environment and a remembered API is exactly the kind of claim this estate
    has been burned by. The constants above name the file and line each value
    came from.

    WHAT IS NOT VERIFIED, AND WHY THE DESIGN SURVIVES IT

    Three things cannot be settled without a live call: whether `timestamps`
    events interleave with `chunk` events or arrive in a clump, which model id
    the account is entitled to, and what the service does under its own rate
    limit. So the face is NOT built on word timings. It is built on the
    amplitude of the audio actually received, sliced at 60 frames per second,
    which is on the audio timeline by construction and cannot desynchronise
    however the events are ordered. Word timings, when they arrive in time,
    only choose WHICH shape the envelope opens. If they never arrive, the mouth
    still moves with the voice on a neutral shape. If they arrive late, the
    frames already sent were merely less articulate, never wrong.

    The three envelope constants are calibrated against synthetic tones, which
    proves the arithmetic and not the taste. Tuning them is a job for a human
    watching a real reply, and that is the same live readback that settles the
    rest.

    ONE CLIENT PER CALL, DELIBERATELY

    `apps/presence/main.py` has no lifespan hook, so a client held on this
    object would never be closed. A turn already costs an inference round trip,
    so a handshake per reply is a smaller price than a connection pool nothing
    owns.
    """

    name = "cartesia"

    def __init__(
        self,
        api_key: str,
        voice_id: str,
        *,
        model: str = DEFAULT_CARTESIA_MODEL,
        language: str = "en",
        fps: int = 60,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        if not (api_key or "").strip():
            raise SpeechNotConfigured(
                "PRESENCE_SPEECH is cartesia but CARTESIA_API_KEY is empty."
            )
        if not (voice_id or "").strip():
            raise SpeechNotConfigured(CARTESIA_VOICE_RULE)
        if fps <= 0:
            raise ValueError("fps must be greater than zero")
        self._api_key = api_key.strip()
        self.voice_id = voice_id.strip()
        self.model = (model or DEFAULT_CARTESIA_MODEL).strip() or DEFAULT_CARTESIA_MODEL
        self.language = (language or "en").strip() or "en"
        self.fps = fps
        self._transport = transport

    @property
    def configured(self) -> bool:
        return bool(self._api_key and self.voice_id)

    def headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Cartesia-Version": CARTESIA_VERSION,
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }

    def request_body(self, text: str, turn: str) -> Dict[str, Any]:
        """The JSON body for one reply. Pure, so a test can read it."""
        return {
            "model_id": self.model,
            "transcript": text,
            "voice": {"id": self.voice_id},
            "output_format": dict(CARTESIA_OUTPUT_FORMAT),
            "language": self.language,
            "add_timestamps": True,
            "context_id": turn,
        }

    async def _events(self, text: str, turn: str) -> AsyncIterator[Dict[str, Any]]:
        """Every decoded SSE event from one request, in arrival order."""
        timeout = httpx.Timeout(
            CARTESIA_READ_TIMEOUT_S, connect=CARTESIA_CONNECT_TIMEOUT_S
        )
        async with httpx.AsyncClient(timeout=timeout, transport=self._transport) as client:
            async with client.stream(
                "POST",
                CARTESIA_TTS_URL,
                headers=self.headers(),
                json=self.request_body(text, turn),
            ) as response:
                if response.status_code >= 400:
                    # The status and a fixed hint, never the vendor's body.
                    #
                    # A critic put a 401 through this on 2026-09-09 whose body
                    # echoed both the Authorization header and the request, and
                    # watched the key and Tee's transcript come out in the
                    # exception text. `session.py:302` sends `str(exc)` to the
                    # socket, and the only reason it missed the logger there is
                    # that `run_turn` catches SpeechNotConfigured one frame
                    # before `logger.exception`. Whether Cartesia really echoes
                    # a bearer token is unverified and unlikely; forwarding
                    # nothing is cheaper than finding out.
                    await response.aread()
                    raise SpeechNotConfigured(
                        f"Cartesia refused the request with HTTP "
                        f"{response.status_code}. The vendor's response body is "
                        "not forwarded, because it can echo the request and the "
                        f"key. {_status_hint(response.status_code)}"
                    )
                block: List[str] = []
                async for line in response.aiter_lines():
                    block.append(line)
                    if line.strip():
                        continue
                    for payload in sse_payloads(block):
                        event = _decode_event(payload)
                        if event is not None:
                            yield event
                    block = []
                for payload in sse_payloads(block):
                    event = _decode_event(payload)
                    if event is not None:
                        yield event

    async def synthesize(self, text: str, turn: str) -> AsyncIterator[SpeechChunk]:
        yield SpeechChunk(kind=CHUNK_STATE, at_ms=0.0, state=STATE_SPEAKING)
        spoken = (text or "").strip()
        if not spoken:
            yield SpeechChunk(kind=CHUNK_STATE, at_ms=0.0, state=STATE_DONE)
            return

        clock = WordClock()
        cursor_samples = 0
        # Per turn, not per chunk and not on self: the residual belongs to one
        # reply, and a slicer held on the object would carry one turn's leftover
        # samples into the next.
        slicer = FrameSlicer(self.fps)
        # aclosing, not a bare `async for`: the loop below breaks on the done
        # event, and without this the inner generator would stay suspended with
        # its client open until the event loop's finaliser got round to it.
        #
        # Scope, measured by a critic on 2026-09-09 rather than assumed. This
        # protects `_events` from `synthesize`; it does not protect `synthesize`
        # from its own consumer. Counting transport closes: a consumer that runs
        # to completion closes immediately, a consumer cancelled at its own await
        # closes after one loop turn, and a consumer that breaks out of the
        # `async for` and returns closes only at garbage collection. The last
        # case has no caller today, because `session.py` cancels the producer and
        # then awaits it, which is the second shape. So the claim is "the socket
        # does not outlive the turn by more than a loop turn", not "the socket's
        # lifetime is the turn's".
        async with aclosing(self._events(spoken, turn)) as events:
            async for event in events:
                kind = event.get("type")
                if kind == "timestamps":
                    clock.extend(event.get("word_timestamps"))
                    continue
                if kind == "error":
                    raise SpeechNotConfigured(
                        "Cartesia returned an error event: "
                        f"{event.get('title') or ''} {event.get('message') or ''}".strip()
                    )
                if kind == "done":
                    break
                if kind != "chunk":
                    # phoneme_timestamps and anything a later API version adds.
                    continue
                pcm = _decode_audio(event.get("data"))
                if not pcm:
                    continue
                at_ms = cursor_samples / AUDIO_RATE * 1000.0
                yield SpeechChunk(kind=CHUNK_AUDIO, at_ms=round(at_ms, 3), pcm=pcm)
                for frame in slicer.push(pcm, cursor_samples, clock):
                    yield frame
                cursor_samples += len(pcm) // 2

        # A tail shorter than one frame still plays, so it still gets a face.
        for frame in slicer.flush(clock):
            yield frame

        total_ms = cursor_samples / AUDIO_RATE * 1000.0
        yield SpeechChunk(kind=CHUNK_STATE, at_ms=round(total_ms, 3), state=STATE_DONE)


def _status_hint(status: int) -> str:
    """What an operator should check, keyed on the status alone.

    Deliberately from the status code rather than from the vendor's message: a
    hint this module wrote cannot leak anything the vendor put in its body.
    """
    if status in (401, 403):
        return "Check CARTESIA_API_KEY on the presence service."
    if status == 402:
        return "The Cartesia account may be out of credit."
    if status == 404:
        return "Check CARTESIA_MODEL and CARTESIA_VOICE_ID; one may not exist."
    if status == 422:
        return "Cartesia rejected the request shape, so this build's contract may be stale."
    if status == 429:
        return "Rate limited by Cartesia. The free tier is 5 requests a minute."
    if status >= 500:
        return "Cartesia is failing on its side. Retrying later is the only fix here."
    return "Read the Cartesia dashboard for the request id."


def _decode_event(payload: str) -> Optional[Dict[str, Any]]:
    """One SSE payload as a dict, or None when it is not one.

    A malformed frame must not kill a reply that is already speaking, so this
    declines rather than raising. A stream that is entirely malformed produces
    no audio and the session reports a turn that said nothing, which is visible.
    """
    body = payload.strip()
    if not body or body == "[DONE]":
        return None
    try:
        parsed = json.loads(body)
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _decode_audio(data: Any) -> bytes:
    if not isinstance(data, str) or not data:
        return b""
    try:
        return base64.b64decode(data, validate=True)
    except (ValueError, TypeError):
        return b""


def build_speech(settings: PresenceSettings) -> SpeechSynthesizer:
    """The configured synthesiser. A missing key or voice fails at startup, by name."""
    if settings.PRESENCE_SPEECH == "mock":
        return MockSpeech()
    if settings.PRESENCE_SPEECH == "cartesia":
        if not settings.CARTESIA_API_KEY:
            raise SpeechNotConfigured(
                "PRESENCE_SPEECH is cartesia but CARTESIA_API_KEY is empty. Set the key "
                "or switch PRESENCE_SPEECH to mock."
            )
        if not settings.CARTESIA_VOICE_ID:
            raise SpeechNotConfigured(CARTESIA_VOICE_RULE)
        return CartesiaSpeech(
            settings.CARTESIA_API_KEY,
            settings.CARTESIA_VOICE_ID,
            model=settings.CARTESIA_MODEL,
            language=settings.CARTESIA_LANGUAGE,
        )
    raise SpeechNotConfigured(f"unknown PRESENCE_SPEECH {settings.PRESENCE_SPEECH!r}")

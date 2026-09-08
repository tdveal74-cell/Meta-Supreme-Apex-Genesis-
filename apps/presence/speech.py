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

``CartesiaSpeech`` is a stub. Its constructor accepts the key; its
``synthesize`` raises ``SpeechNotConfigured`` naming the gate. The
vendor's request and response shapes were not verified in this build and
are not guessed at here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import AsyncIterator, Dict, List, Protocol, Tuple

from apps.presence.protocol import AUDIO_RATE, PRIORITY_EXPRESSION, PRIORITY_LIP_SYNC
from apps.presence.settings import PresenceSettings

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
        """Triangular blink envelope, 0 outside a blink."""
        if at_ms < self.blink_offset_ms or self.blink_every_ms <= 0 or self.blink_ms <= 0:
            return 0.0
        phase = (at_ms - self.blink_offset_ms) % self.blink_every_ms
        if phase >= self.blink_ms:
            return 0.0
        half = self.blink_ms / 2.0
        return round(1.0 - abs(phase - half) / half, 3)

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
# Cartesia: stub until the vendor shape is verified
# ---------------------------------------------------------------------------

CARTESIA_GATE = (
    "Cartesia adapter is a stub: the vendor response shape was not verified in "
    "this build. Set PRESENCE_SPEECH=mock until the adapter is built against a "
    "recorded Cartesia response."
)


class CartesiaSpeech:
    """Placeholder for the Cartesia adapter. Refuses to speak, by name."""

    name = "cartesia"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key or ""

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    async def synthesize(self, text: str, turn: str) -> AsyncIterator[SpeechChunk]:
        raise SpeechNotConfigured(CARTESIA_GATE)
        yield SpeechChunk(kind=CHUNK_STATE, at_ms=0.0)  # pragma: no cover - keeps this a generator


def build_speech(settings: PresenceSettings) -> SpeechSynthesizer:
    """The configured synthesiser. A missing Cartesia key fails at startup, by name."""
    if settings.PRESENCE_SPEECH == "mock":
        return MockSpeech()
    if settings.PRESENCE_SPEECH == "cartesia":
        if not settings.CARTESIA_API_KEY:
            raise SpeechNotConfigured(
                "PRESENCE_SPEECH is cartesia but CARTESIA_API_KEY is empty. Set the key "
                "or switch PRESENCE_SPEECH to mock. " + CARTESIA_GATE
            )
        return CartesiaSpeech(settings.CARTESIA_API_KEY)
    raise SpeechNotConfigured(f"unknown PRESENCE_SPEECH {settings.PRESENCE_SPEECH!r}")

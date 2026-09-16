"""Transcription: a clip of the user's voice in, text out.

This is the ear that protocol v2 adds. Until it, the presence socket had a
mouth (`speech.py`), a face (`protocol.validate_frame`) and a brain
(`inference.py`), and no way to hear at all: the client sent `say` with text
it already had, `main.py` only ever called `receive_text`, and the
`listening` session state was a label on a text box.

A ``Transcriber`` takes the assembled bytes of one push to talk clip and
returns a ``HeardClip``. The session then runs that text through the same
``begin_turn`` a typed ``say`` runs, which is the whole reason v2 adds no
new surface that can act: speaking a turn and typing it converge one
function later.

``MockHearing`` is deterministic and needs no network or key, so the socket,
the clip assembly and the turn it starts can all be exercised end to end
without spending a vendor call. It reports ``confidence`` of None by
default, because it has none, and a transcriber that invented one would hide
exactly the null handling most likely to break.

``ElevenLabsHearing`` is the real one, and the same vendor the devon-hears
n8n lane already uses, so the estate has one transcription bill and one
place to reason about accuracy.

What is verified here and what is not, stated plainly:

- The response shape IS measured. Execution 296 on 2026-09-16 drove a real
  voice note through this vendor on the live account and returned ``text``,
  ``language_code``, ``language_probability`` and a ``words`` array carrying
  per word logprobs. ``language_probability`` is what this module reads as
  confidence, and it came back 1.0 on clean speech.
- The request shape is NOT executed from this repository. ``elevenlabs.io``
  is blocked by this container's network egress proxy, so the endpoint,
  the ``xi-api-key`` header, the multipart ``file`` and ``model_id`` fields
  and the ``scribe_v1`` model id were taken from a secondary source rather
  than read from the vendor. One clip through ``PRESENCE_EARS=elevenlabs``
  against the live key settles it. Until someone runs that, the default
  stays ``mock`` so nothing depends silently on an unexecuted path.

The vendor's error body is never forwarded. That rule is not caution, it is
a measured finding: a critic put a 401 through the Cartesia path on
2026-09-09 and watched the response body echo the Authorization header and
the transcript back out through ``session.py``, which sends ``str(exc)`` to
the socket. The same shape applies here with the user's own voice in it.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import List, Optional, Protocol, Sequence

import httpx

from apps.presence.settings import PresenceSettings

#: Read from a secondary source on 2026-09-16; see the module docstring for
#: what that means and what would settle it.
ELEVENLABS_STT_URL = "https://api.elevenlabs.io/v1/speech-to-text"

#: The two transcription models the vendor exposes. ``scribe_v1`` is the
#: stable one. The n8n node's own model picker lists SYNTHESIS models only,
#: measured 2026-09-16, which is why that node leaves the field unset and why
#: this one cannot borrow its answer.
ELEVENLABS_STT_MODELS = ("scribe_v1", "scribe_v1_experimental")
DEFAULT_STT_MODEL = "scribe_v1"

STT_CONNECT_TIMEOUT_S = 10.0
STT_READ_TIMEOUT_S = 120.0

#: What `build_hearing` will answer to.
HEARING_CHOICES = ("mock", "elevenlabs")


class HearingNotConfigured(RuntimeError):
    """Raised when the configured ear cannot transcribe, naming the setting."""


class HearingFailed(RuntimeError):
    """The vendor was reached and did not return a transcript.

    Separate from ``HearingNotConfigured`` because they need different
    answers: a misconfiguration is the operator's, a failed call is this
    turn's and the socket stays open for the next one.
    """


class ClipTooLarge(RuntimeError):
    """One clip outgrew its cap mid upload. Carries what the cap was."""


@dataclass
class ClipInProgress:
    """One push to talk clip, assembled between listen_start and listen_end.

    Held per socket, not per session object, because a clip is in flight only
    between two client messages and has nothing to say to a turn that is
    already running.

    The caps are checked BEFORE the chunk is kept, so the ceiling is a
    ceiling rather than a report of how far past it we already went. A clip
    that breaches one is dropped whole: transcribing the part that arrived
    would return a fluent sentence that is not what was said, which is worse
    than an error because nothing downstream can tell it apart from a good
    one.
    """

    turn_id: Optional[str] = None
    codec: str = ""
    rate: int = 0
    chunks: List[bytes] = field(default_factory=list)
    total_bytes: int = 0

    @property
    def is_open(self) -> bool:
        return self.turn_id is not None

    def start(self, turn_id: str, codec: str, rate: int) -> None:
        self.turn_id = turn_id
        self.codec = codec
        self.rate = int(rate or 0)
        self.chunks = []
        self.total_bytes = 0

    def owns(self, turn_id: str) -> bool:
        return self.is_open and self.turn_id == turn_id

    def append(self, audio: bytes, *, max_bytes: int, max_chunks: int) -> None:
        if len(self.chunks) + 1 > max_chunks:
            raise ClipTooLarge(
                f"this clip is over {max_chunks} chunks and was dropped. Send "
                "fewer, larger chunks or a shorter clip."
            )
        if self.total_bytes + len(audio) > max_bytes:
            raise ClipTooLarge(
                f"this clip is over {max_bytes} bytes and was dropped. Record a "
                "shorter one."
            )
        self.chunks.append(audio)
        self.total_bytes += len(audio)

    def finish(self) -> bytes:
        return b"".join(self.chunks)

    def reset(self) -> None:
        self.turn_id = None
        self.codec = ""
        self.rate = 0
        self.chunks = []
        self.total_bytes = 0


@dataclass(frozen=True)
class HeardClip:
    """One transcription. ``confidence`` is None when none was reported."""

    text: str
    confidence: Optional[float] = None
    provider: str = "mock"
    language: Optional[str] = None


class Transcriber(Protocol):
    name: str

    async def transcribe(self, audio: bytes, *, codec: str, rate: int) -> HeardClip: ...


# ---------------------------------------------------------------------------
# Containers


def wav_from_pcm(pcm: bytes, rate: int, *, channels: int = 1) -> bytes:
    """Wrap raw little endian 16 bit PCM in a RIFF header.

    The client's AudioWorklet lane sends headerless samples, and a
    transcription endpoint takes a file, not a bare buffer. Without this the
    vendor gets 16 kHz of samples it has to guess the shape of, and guessing
    wrong sounds like speech played at the wrong speed, which transcribes to
    confident nonsense rather than to an error.
    """
    if rate <= 0:
        raise ValueError("rate must be greater than zero")
    if channels <= 0:
        raise ValueError("channels must be greater than zero")
    bits = 16
    block_align = channels * bits // 8
    byte_rate = rate * block_align
    return b"".join(
        (
            b"RIFF",
            struct.pack("<I", 36 + len(pcm)),
            b"WAVEfmt ",
            struct.pack("<IHHIIHH", 16, 1, channels, rate, byte_rate, block_align, bits),
            b"data",
            struct.pack("<I", len(pcm)),
            pcm,
        )
    )


def upload_for(audio: bytes, codec: str, rate: int) -> tuple:
    """(filename, bytes, content type) for one clip, by declared codec.

    The codec is declared by the client in ``listen_start`` and carried here
    rather than sniffed, so a mislabelled clip fails as a mislabelled clip.
    """
    if codec == "pcm_s16le":
        return ("clip.wav", wav_from_pcm(audio, rate), "audio/wav")
    if codec == "webm_opus":
        return ("clip.webm", audio, "audio/webm")
    raise HearingFailed(f"no upload shape for codec {codec!r}")


# ---------------------------------------------------------------------------
# Transcribers


class MockHearing:
    """Deterministic, no network, no key. Cycles a script one line per call."""

    name = "mock"

    def __init__(
        self,
        script: Optional[Sequence[str]] = None,
        *,
        confidence: Optional[float] = None,
    ) -> None:
        lines = list(script or ["what time is it"])
        if not lines:
            raise ValueError("script cannot be empty")
        self._script: List[str] = lines
        self._calls = 0
        self._confidence = confidence
        self.heard: List[bytes] = []

    async def transcribe(self, audio: bytes, *, codec: str, rate: int) -> HeardClip:
        if not audio:
            raise HearingFailed("no audio arrived, so there was nothing to transcribe")
        self.heard.append(audio)
        text = self._script[self._calls % len(self._script)]
        self._calls += 1
        return HeardClip(
            text=text, confidence=self._confidence, provider=self.name, language="eng"
        )


class ElevenLabsHearing:
    """The vendor the devon-hears lane already uses, called directly."""

    name = "elevenlabs"

    def __init__(
        self,
        api_key: str,
        *,
        model: str = DEFAULT_STT_MODEL,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        if not (api_key or "").strip():
            raise HearingNotConfigured(
                "PRESENCE_EARS is elevenlabs but ELEVENLABS_API_KEY is empty. Set "
                "the key or switch PRESENCE_EARS to mock."
            )
        chosen = (model or DEFAULT_STT_MODEL).strip() or DEFAULT_STT_MODEL
        if chosen not in ELEVENLABS_STT_MODELS:
            raise HearingNotConfigured(
                f"ELEVENLABS_STT_MODEL is {chosen!r}; it must be one of "
                f"{', '.join(ELEVENLABS_STT_MODELS)}. The vendor's synthesis "
                "models cannot transcribe, and naming one here would fail per "
                "clip rather than at startup."
            )
        self._api_key = api_key.strip()
        self.model = chosen
        self._transport = transport

    def headers(self) -> dict:
        return {"xi-api-key": self._api_key}

    async def transcribe(self, audio: bytes, *, codec: str, rate: int) -> HeardClip:
        if not audio:
            raise HearingFailed("no audio arrived, so there was nothing to transcribe")
        filename, payload, content_type = upload_for(audio, codec, rate)
        timeout = httpx.Timeout(STT_READ_TIMEOUT_S, connect=STT_CONNECT_TIMEOUT_S)
        async with httpx.AsyncClient(timeout=timeout, transport=self._transport) as client:
            response = await client.post(
                ELEVENLABS_STT_URL,
                headers=self.headers(),
                data={"model_id": self.model},
                files={"file": (filename, payload, content_type)},
            )
            if response.status_code >= 400:
                # The status and a fixed hint, never the vendor's body. See the
                # module docstring: the Cartesia path proved a 401 body can
                # carry the key and the user's words back out onto the socket.
                raise HearingFailed(
                    f"the transcriber refused the clip with HTTP "
                    f"{response.status_code}. The vendor's response body is not "
                    "forwarded, because it can echo the request and the key."
                )
            try:
                body = response.json()
            except ValueError as exc:
                raise HearingFailed(
                    "the transcriber answered with something that is not JSON"
                ) from exc

        text = body.get("text")
        if not isinstance(text, str) or not text.strip():
            raise HearingFailed(
                "the transcriber returned no text for this clip. Nothing is "
                "guessed from an empty transcript."
            )
        return HeardClip(
            text=text.strip(),
            confidence=_confidence_of(body),
            provider=self.name,
            language=body.get("language_code") if isinstance(body.get("language_code"), str) else None,
        )


def _confidence_of(body: dict) -> Optional[float]:
    """``language_probability`` as a float, or None when it is not a number.

    None rather than 0.0 on anything unexpected. A zero reads downstream as
    "heard, and certain it was nothing", which is the opposite of "the
    transcriber did not say".
    """
    value = body.get("language_probability")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if number != number or number in (float("inf"), float("-inf")):
        return None
    if not 0.0 <= number <= 1.0:
        return None
    return number


def build_hearing(settings: PresenceSettings) -> Transcriber:
    """The configured ear. A missing key fails at startup, by name."""
    if settings.PRESENCE_EARS == "mock":
        return MockHearing()
    if settings.PRESENCE_EARS == "elevenlabs":
        return ElevenLabsHearing(
            settings.ELEVENLABS_API_KEY, model=settings.ELEVENLABS_STT_MODEL
        )
    raise HearingNotConfigured(f"unknown PRESENCE_EARS {settings.PRESENCE_EARS!r}")

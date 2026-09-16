"""Wire protocol for the presence WebSocket, v2.

Every message is one JSON text frame with a ``t`` field naming its type.
The shapes here are the contract the web client is built against, so a
field is renamed only by bumping ``PROTOCOL_VERSION`` and shipping both
sides together.

v2 adds an ear. Until it, this socket had a mouth and a face and no way to
hear: ``CLIENT_TYPES`` carried no audio type, ``main.py`` only ever called
``receive_text``, and the ``listening`` state was a label on a text box.
``listen_start``, ``listen_chunk`` and ``listen_end`` carry one push to
talk clip up, the server transcribes it, and the text enters the same
``begin_turn`` a typed ``say`` enters. Speaking a turn and typing it reach
the same code, so v2 adds no surface that can act.

**The version is negotiated, not pinned.** v1 refused a hello whose
``protocol`` was not the server's own, and ``apps/web/lib/presence/protocol.ts``
refuses a ``ready`` whose protocol is not the client's own. Those two pins
face each other, so bumping one side alone stops the page connecting at
all, in both directions, and the web app and this service deploy
separately. The server therefore accepts any version in
``SUPPORTED_PROTOCOLS`` and echoes back the one the client asked for. A v1
client keeps seeing 1, keeps working, and gets a session that refuses the
listen types by name. That is what lets this service ship before the client
rather than in lockstep with it.

Client to server::

    {"t": "hello", "token": "<DEVON access JWT>", "client": "web", "protocol": 1|2}
    {"t": "say", "turn_id": "<client uuid>", "text": "..."}
    {"t": "listen_start", "turn_id": "...", "codec": "pcm_s16le", "rate": 16000}  [v2]
    {"t": "listen_chunk", "turn_id": "...", "seq": <int from 0>, "b64": "..."}    [v2]
    {"t": "listen_end", "turn_id": "..."}                                        [v2]
    {"t": "interrupt", "turn_id": "...", "at_ms": <client performance.now()>}
    {"t": "render", "turn_id": "...", "behind_ms": <number>, "fps": <number>}
    {"t": "ping", "at_ms": <number>}

Server to client::

    {"t": "ready", "session_id", "protocol", "speech", "inference", "fallback",
     "livekit": {"configured": bool, "url": str | null}}
    {"t": "state", "state": "idle|listening|thinking|speaking", "turn_id", "at_ms"}
    {"t": "transcript", "turn_id", "text", "confidence", "provider"}              [v2]
    {"t": "token", "turn_id", "text"}
    {"t": "frame", "turn_id", "seq", "at_ms", "priority": 0|1|2, "weights": {...}}
    {"t": "audio", "turn_id", "seq", "at_ms", "codec": "pcm_s16le", "rate": 16000, "b64"}
    {"t": "interrupt_ack", "turn_id", "flushed_frames", "server_latency_ms"}
    {"t": "metrics", "turn_id", "provider", "fell_back", "ttft_ms", "breaker",
     "frames_sent", "frames_dropped", "tokens"}
    {"t": "pong", "at_ms": <echo>, "server_ms"}
    {"t": "error", "code", "message"}

``transcript`` goes out before the turn runs, so the client can show what
was heard even if inference then fails. ``confidence`` is null when the
transcriber did not report one; it is never defaulted to a number, because
a zero and an unreported value look the same to a reader and mean opposite
things.

Frame weights use the 52 ARKit blendshape names only, values 0..1.
``validate_frame`` refuses anything else by naming it; nothing is clamped
or silently dropped, because a clamped 1.4 and a genuine 1.0 look the same
on the face and different in the log.

Priorities decide what the buffer sheds first when the renderer falls
behind: 0 is lip sync (jaw, mouth, cheekPuff, tongueOut), 1 is expression
(brows, eyes, cheek squint, nose sneer), 2 is ambient motion. Nothing in
this build emits priority 2; the slot exists so idle motion can be added
without renumbering.
"""

from __future__ import annotations

import base64
import binascii
import json
import time
from typing import Any, Dict, List, Mapping, Optional, Tuple, TypedDict

PROTOCOL_VERSION = 2

#: Every version this server will negotiate. A hello naming any of these is
#: accepted and `ready` echoes that same number back, so an older client keeps
#: the contract it was built against instead of being refused at the door.
SUPPORTED_PROTOCOLS: Tuple[int, ...] = (1, 2)

#: The version a message type first appeared in. A session negotiated below a
#: type's version is refused that type by name rather than quietly ignoring it.
TYPE_MIN_PROTOCOL: Dict[str, int] = {
    "listen_start": 2,
    "listen_chunk": 2,
    "listen_end": 2,
}

#: The 52 ARKit face blendshapes, camelCase, in Apple's documented order.
ARKIT_BLENDSHAPES: Tuple[str, ...] = (
    "eyeBlinkLeft",
    "eyeLookDownLeft",
    "eyeLookInLeft",
    "eyeLookOutLeft",
    "eyeLookUpLeft",
    "eyeSquintLeft",
    "eyeWideLeft",
    "eyeBlinkRight",
    "eyeLookDownRight",
    "eyeLookInRight",
    "eyeLookOutRight",
    "eyeLookUpRight",
    "eyeSquintRight",
    "eyeWideRight",
    "jawForward",
    "jawLeft",
    "jawRight",
    "jawOpen",
    "mouthClose",
    "mouthFunnel",
    "mouthPucker",
    "mouthLeft",
    "mouthRight",
    "mouthSmileLeft",
    "mouthSmileRight",
    "mouthFrownLeft",
    "mouthFrownRight",
    "mouthDimpleLeft",
    "mouthDimpleRight",
    "mouthStretchLeft",
    "mouthStretchRight",
    "mouthRollLower",
    "mouthRollUpper",
    "mouthShrugLower",
    "mouthShrugUpper",
    "mouthPressLeft",
    "mouthPressRight",
    "mouthLowerDownLeft",
    "mouthLowerDownRight",
    "mouthUpperUpLeft",
    "mouthUpperUpRight",
    "browDownLeft",
    "browDownRight",
    "browInnerUp",
    "browOuterUpLeft",
    "browOuterUpRight",
    "cheekPuff",
    "cheekSquintLeft",
    "cheekSquintRight",
    "noseSneerLeft",
    "noseSneerRight",
    "tongueOut",
)

PRIORITY_LIP_SYNC = 0
PRIORITY_EXPRESSION = 1
PRIORITY_AMBIENT = 2
FRAME_PRIORITIES = (PRIORITY_LIP_SYNC, PRIORITY_EXPRESSION, PRIORITY_AMBIENT)


def _priority_for_name(name: str) -> int:
    if name.startswith(("jaw", "mouth")) or name in ("cheekPuff", "tongueOut"):
        return PRIORITY_LIP_SYNC
    return PRIORITY_EXPRESSION


#: Per blendshape priority: 0 for jaw*, mouth*, cheekPuff, tongueOut; 1 for
#: brow*, eye*, cheekSquint*, noseSneer*.
PRIORITY_OF: Dict[str, int] = {name: _priority_for_name(name) for name in ARKIT_BLENDSHAPES}


class FrameValidationError(ValueError):
    """A frame named an unknown blendshape or carried a weight outside 0..1."""


def validate_frame(weights: Mapping[str, Any]) -> Dict[str, float]:
    """Return a clean copy of ``weights`` or raise naming every offender.

    Booleans are refused even though Python counts them as integers: a
    ``True`` where a weight belongs is a bug upstream, not a 1.0.
    """
    if not isinstance(weights, Mapping):
        raise FrameValidationError(
            f"frame weights must be a mapping of blendshape to weight, got {type(weights).__name__}"
        )
    unknown: List[str] = []
    not_numbers: List[str] = []
    out_of_range: List[str] = []
    cleaned: Dict[str, float] = {}
    for name, value in weights.items():
        if name not in PRIORITY_OF:
            unknown.append(str(name))
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            not_numbers.append(f"{name}={value!r}")
            continue
        number = float(value)
        if number != number or number < 0.0 or number > 1.0:
            out_of_range.append(f"{name}={value}")
            continue
        cleaned[name] = number
    problems: List[str] = []
    if unknown:
        problems.append("unknown blendshape(s): " + ", ".join(sorted(unknown)))
    if not_numbers:
        problems.append("non numeric weight(s): " + ", ".join(not_numbers))
    if out_of_range:
        problems.append("weight(s) outside 0..1: " + ", ".join(out_of_range))
    if problems:
        raise FrameValidationError("; ".join(problems))
    return cleaned


def priority_for_frame(weights: Mapping[str, Any]) -> int:
    """The frame's priority is that of its most important shape."""
    priorities = [PRIORITY_OF[name] for name in weights if name in PRIORITY_OF]
    return min(priorities) if priorities else PRIORITY_AMBIENT


def server_ms() -> float:
    """Server monotonic milliseconds. Only differences between two readings mean anything."""
    return time.monotonic() * 1000.0


# ---------------------------------------------------------------------------
# Client messages
# ---------------------------------------------------------------------------

CLIENT_TYPES = (
    "hello",
    "say",
    "listen_start",
    "listen_chunk",
    "listen_end",
    "interrupt",
    "render",
    "ping",
)

HELLO_TIMEOUT_SECONDS = 15.0
MAX_SAY_CHARS = 4000
MAX_TURN_ID_CHARS = 128
MAX_MESSAGE_CHARS = 64_000

#: What a client may declare it is sending up. `pcm_s16le` is what an
#: AudioWorklet produces and what this service already speaks downstream;
#: `webm_opus` is what MediaRecorder gives by default with no conversion in
#: the page. The transcriber is told which, never left to sniff it.
LISTEN_CODECS = ("pcm_s16le", "webm_opus")

#: Sample rates accepted for raw PCM. Ignored for a container format, which
#: carries its own.
LISTEN_RATES = (16000, 24000, 44100, 48000)

#: The ceiling on one clip, counted in decoded bytes as chunks arrive. At
#: 16 kHz mono s16le this is a bit over four minutes, which is long for push
#: to talk and short enough that a client cannot spend the process's memory.
#: The check runs BEFORE the chunk is appended, so the cap is a cap and not a
#: report of how far past it we already are.
MAX_CLIP_BYTES = 8 * 1024 * 1024

#: A second ceiling on the same clip, because a flood of tiny chunks costs
#: per message work that the byte cap alone would not bound.
MAX_CLIP_CHUNKS = 512

#: WebSocket close codes, matching app/api/v1/operator_shell.py.
CLOSE_MALFORMED = 4400
CLOSE_UNAUTHENTICATED = 4401

#: Codes carried by the ``error`` message. The first two mirror the close
#: codes; the 45xx codes describe a turn that failed on an open socket.
ERR_MALFORMED = 4400
ERR_UNAUTHENTICATED = 4401
ERR_INFERENCE_UNAVAILABLE = 4500
ERR_SPEECH_NOT_CONFIGURED = 4501
ERR_TURN_FAILED = 4502
#: v2. A clip that outgrew MAX_CLIP_BYTES or MAX_CLIP_CHUNKS mid upload. The
#: partial clip is dropped rather than transcribed, because half an utterance
#: transcribes to a confident wrong sentence rather than to an error.
ERR_CLIP_TOO_LARGE = 4503
#: v2. The transcriber was reached and returned no usable text. The socket
#: stays open; this is one turn failing, not the session.
ERR_HEARING_FAILED = 4504
#: v2. A message type the session's negotiated protocol does not carry. Named
#: rather than ignored, so a client mismatched with the server learns which.
ERR_PROTOCOL_TOO_OLD = 4505


class ProtocolError(ValueError):
    """A client message that does not fit the protocol. Carries an error code."""

    def __init__(self, message: str, code: int = ERR_MALFORMED) -> None:
        super().__init__(message)
        self.code = code


def _require_str(message: Mapping[str, Any], key: str, *, max_chars: int) -> str:
    value = message.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ProtocolError(f"{message.get('t')}: {key} must be a non empty string")
    if len(value) > max_chars:
        raise ProtocolError(f"{message.get('t')}: {key} is longer than {max_chars} characters")
    return value


def _require_number(message: Mapping[str, Any], key: str) -> float:
    value = message.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProtocolError(f"{message.get('t')}: {key} must be a number")
    try:
        number = float(value)
    except OverflowError as exc:
        raise ProtocolError(f"{message.get('t')}: {key} must be a finite number") from exc
    # json.loads admits NaN and Infinity, and an integer too large for a
    # float. None can go back out (the sender refuses them) and an infinite
    # behind_ms poisoned every later turn.
    if number != number or number in (float("inf"), float("-inf")):
        raise ProtocolError(f"{message.get('t')}: {key} must be a finite number")
    return number


def parse_client_message(raw: str) -> Dict[str, Any]:
    """Parse one client frame or raise ProtocolError saying what was wrong."""
    if len(raw) > MAX_MESSAGE_CHARS:
        raise ProtocolError(f"message is longer than {MAX_MESSAGE_CHARS} characters")
    try:
        message = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProtocolError(f"message is not valid JSON: {exc.msg}") from exc
    if not isinstance(message, dict):
        raise ProtocolError("message must be a JSON object")
    kind = message.get("t")
    if kind not in CLIENT_TYPES:
        raise ProtocolError(
            f"unknown message type {kind!r}; expected one of {', '.join(CLIENT_TYPES)}"
        )
    if kind == "hello":
        _require_str(message, "token", max_chars=8192)
        protocol = message.get("protocol")
        if isinstance(protocol, bool) or protocol not in SUPPORTED_PROTOCOLS:
            raise ProtocolError(
                "hello: protocol must be one of "
                f"{', '.join(str(v) for v in SUPPORTED_PROTOCOLS)}, got {protocol!r}"
            )
        client = message.get("client", "")
        if not isinstance(client, str):
            raise ProtocolError("hello: client must be a string")
    elif kind == "say":
        _require_str(message, "turn_id", max_chars=MAX_TURN_ID_CHARS)
        _require_str(message, "text", max_chars=MAX_SAY_CHARS)
    elif kind == "listen_start":
        _require_str(message, "turn_id", max_chars=MAX_TURN_ID_CHARS)
        codec = message.get("codec")
        if codec not in LISTEN_CODECS:
            raise ProtocolError(
                f"listen_start: codec must be one of {', '.join(LISTEN_CODECS)}, "
                f"got {codec!r}"
            )
        if codec == "pcm_s16le":
            rate = message.get("rate")
            if isinstance(rate, bool) or rate not in LISTEN_RATES:
                raise ProtocolError(
                    "listen_start: rate must be one of "
                    f"{', '.join(str(r) for r in LISTEN_RATES)} for pcm_s16le, "
                    f"got {rate!r}"
                )
    elif kind == "listen_chunk":
        _require_str(message, "turn_id", max_chars=MAX_TURN_ID_CHARS)
        seq = message.get("seq")
        if isinstance(seq, bool) or not isinstance(seq, int) or seq < 0:
            raise ProtocolError("listen_chunk: seq must be an integer from zero")
        b64 = message.get("b64")
        if not isinstance(b64, str) or not b64:
            raise ProtocolError("listen_chunk: b64 must be a non empty string")
        try:
            message["audio"] = base64.b64decode(b64, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ProtocolError(f"listen_chunk: b64 is not valid base64: {exc}") from exc
    elif kind == "listen_end":
        _require_str(message, "turn_id", max_chars=MAX_TURN_ID_CHARS)
    elif kind == "interrupt":
        _require_str(message, "turn_id", max_chars=MAX_TURN_ID_CHARS)
        _require_number(message, "at_ms")
    elif kind == "render":
        _require_str(message, "turn_id", max_chars=MAX_TURN_ID_CHARS)
        if _require_number(message, "behind_ms") < 0:
            raise ProtocolError("render: behind_ms cannot be negative")
        _require_number(message, "fps")
    elif kind == "ping":
        _require_number(message, "at_ms")
    return message


# ---------------------------------------------------------------------------
# Server messages
# ---------------------------------------------------------------------------

SERVER_TYPES = (
    "ready",
    "state",
    "transcript",
    "token",
    "frame",
    "audio",
    "interrupt_ack",
    "metrics",
    "pong",
    "error",
)

SESSION_STATES = ("idle", "listening", "thinking", "speaking")

AUDIO_CODEC = "pcm_s16le"
AUDIO_RATE = 16000


class LiveKitInfo(TypedDict):
    configured: bool
    url: Optional[str]


class ReadyMessage(TypedDict):
    t: str
    session_id: str
    protocol: int
    speech: str
    inference: str
    fallback: str
    livekit: LiveKitInfo


class StateMessage(TypedDict):
    t: str
    state: str
    turn_id: Optional[str]
    at_ms: float


class TranscriptMessage(TypedDict):
    t: str
    turn_id: str
    text: str
    confidence: Optional[float]
    provider: str


class TokenMessage(TypedDict):
    t: str
    turn_id: str
    text: str


class FrameMessage(TypedDict):
    t: str
    turn_id: str
    seq: int
    at_ms: float
    priority: int
    weights: Dict[str, float]


class AudioMessage(TypedDict):
    t: str
    turn_id: str
    seq: int
    at_ms: int
    codec: str
    rate: int
    b64: str


class InterruptAckMessage(TypedDict):
    t: str
    turn_id: str
    flushed_frames: int
    server_latency_ms: float


class MetricsMessage(TypedDict):
    t: str
    turn_id: str
    provider: str
    fell_back: bool
    ttft_ms: float
    breaker: str
    frames_sent: int
    frames_dropped: int
    tokens: int


class PongMessage(TypedDict):
    t: str
    at_ms: float
    server_ms: float


class ErrorMessage(TypedDict):
    t: str
    code: int
    message: str


def ready_message(
    *,
    session_id: str,
    speech: str,
    inference: str,
    fallback: str,
    livekit_configured: bool,
    livekit_url: Optional[str],
    protocol: int = PROTOCOL_VERSION,
) -> ReadyMessage:
    """The opening frame. ``protocol`` is the version the CLIENT asked for.

    Echoing the client's number rather than the server's is the whole reason
    an older page keeps working across this bump: `protocol.ts` refuses a
    ready it does not recognise, so a server that always announced its own
    newest version would lock out every client it had not shipped with.
    """
    if protocol not in SUPPORTED_PROTOCOLS:
        raise ValueError(
            f"ready: protocol {protocol!r} is not one of "
            f"{', '.join(str(v) for v in SUPPORTED_PROTOCOLS)}"
        )
    return {
        "t": "ready",
        "session_id": session_id,
        "protocol": protocol,
        "speech": speech,
        "inference": inference,
        "fallback": fallback or "",
        "livekit": {"configured": livekit_configured, "url": livekit_url or None},
    }


def transcript_message(
    turn_id: str,
    text: str,
    *,
    confidence: Optional[float],
    provider: str,
) -> TranscriptMessage:
    """What the server heard, sent before the turn it will now run.

    ``confidence`` stays None when the transcriber reported none. Defaulting
    it to 0.0 would read on the wire as "heard, and certain it was nothing",
    which is the opposite of "did not say".
    """
    return {
        "t": "transcript",
        "turn_id": turn_id,
        "text": text,
        "confidence": confidence,
        "provider": provider,
    }


def state_message(state: str, turn_id: Optional[str]) -> StateMessage:
    if state not in SESSION_STATES:
        raise ValueError(f"unknown session state {state!r}")
    return {"t": "state", "state": state, "turn_id": turn_id, "at_ms": server_ms()}


def token_message(turn_id: str, text: str) -> TokenMessage:
    return {"t": "token", "turn_id": turn_id, "text": text}


def frame_message(
    turn_id: str, seq: int, at_ms: float, priority: int, weights: Mapping[str, float]
) -> FrameMessage:
    if priority not in FRAME_PRIORITIES:
        raise ValueError(f"frame priority must be 0, 1 or 2, got {priority!r}")
    return {
        "t": "frame",
        "turn_id": turn_id,
        "seq": seq,
        "at_ms": at_ms,
        "priority": priority,
        "weights": dict(weights),
    }


def audio_message(turn_id: str, seq: int, at_ms: float, pcm: bytes) -> AudioMessage:
    return {
        "t": "audio",
        "turn_id": turn_id,
        "seq": seq,
        "at_ms": int(at_ms),
        "codec": AUDIO_CODEC,
        "rate": AUDIO_RATE,
        "b64": base64.b64encode(pcm).decode("ascii"),
    }


def interrupt_ack_message(
    turn_id: str, flushed_frames: int, server_latency_ms: float
) -> InterruptAckMessage:
    return {
        "t": "interrupt_ack",
        "turn_id": turn_id,
        "flushed_frames": int(flushed_frames),
        "server_latency_ms": float(server_latency_ms),
    }


def metrics_message(
    *,
    turn_id: str,
    provider: str,
    fell_back: bool,
    ttft_ms: float,
    breaker: str,
    frames_sent: int,
    frames_dropped: int,
    tokens: int,
) -> MetricsMessage:
    return {
        "t": "metrics",
        "turn_id": turn_id,
        "provider": provider,
        "fell_back": bool(fell_back),
        "ttft_ms": float(ttft_ms),
        "breaker": breaker,
        "frames_sent": int(frames_sent),
        "frames_dropped": int(frames_dropped),
        "tokens": int(tokens),
    }


def pong_message(at_ms: float) -> PongMessage:
    return {"t": "pong", "at_ms": at_ms, "server_ms": server_ms()}


def error_message(code: int, message: str) -> ErrorMessage:
    return {"t": "error", "code": int(code), "message": message}

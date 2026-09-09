"""FastAPI entry point for the presence service.

Routes:

- ``GET /health``: liveness plus what is wired (inference, fallback,
  speech, whether LiveKit is configured) and the breaker snapshot.
- ``POST /livekit/token``: a LiveKit join token for the caller, gated on a
  DEVON access JWT. 401 on a bad token, 503 naming the gate when
  LIVEKIT_* is unset.
- ``WS /ws/presence``: protocol v1 from ``protocol.py``. The first frame
  must be ``hello`` within 15 seconds and must carry a DEVON access JWT;
  close 4400 for a malformed hello, 4401 for a bad token, the same codes
  as ``app/api/v1/operator_shell.py``.

``app`` is built from the environment at import. ``create_app`` takes an
explicit ``PresenceSettings`` and lets a test inject the streamers, the
synthesiser and the pacer, so the same routes run against scripted
providers and a virtual clock without touching the environment.

Authentication is verification only. This service never mints a DEVON
token; it checks the one the web client already holds against the shared
SECRET_KEY with the same ``type == "access"`` rule as
``app/security/jwt.py``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, Optional

import jwt
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from apps.presence import SERVICE_NAME
from apps.presence.breaker import CircuitBreaker, InferenceRouter
from apps.presence.inference import TokenStreamer, build_streamer
from apps.presence.livekit_token import DEFAULT_TTL_SECONDS, mint_livekit_token
from apps.presence.protocol import (
    CLOSE_MALFORMED,
    CLOSE_UNAUTHENTICATED,
    ERR_MALFORMED,
    ERR_UNAUTHENTICATED,
    HELLO_TIMEOUT_SECONDS,
    ProtocolError,
    audio_message,
    error_message,
    parse_client_message,
    pong_message,
    ready_message,
)
from apps.presence.session import Pacer, PresenceSession, RealTimePacer
from apps.presence.settings import PresenceConfigError, PresenceSettings
from apps.presence.speech import CHUNK_AUDIO, SpeechSynthesizer, build_speech

logger = logging.getLogger(__name__)


@dataclass
class Runtime:
    """Everything a request handler needs, hung on ``app.state.runtime``."""

    settings: PresenceSettings
    router: InferenceRouter
    speech: SpeechSynthesizer
    pacer: Pacer
    #: Open presence sessions, session id to the DEVON user id that opened
    #: it. A LiveKit token is minted only for a room named here and only to
    #: the user who owns it, so a signed-in user cannot mint a join token
    #: for a room the estate's LiveKit project holds for someone else.
    sessions: Dict[str, str] = field(default_factory=dict)

    @property
    def send_audio_over_websocket(self) -> bool:
        # Protocol v1: audio frames on the socket only when LiveKit is not
        # configured. With LiveKit configured this build sends no audio at
        # all, because the room publisher is a later gate (see the package
        # docstring). That is stated in /health rather than hidden.
        return not self.settings.livekit_configured


def decode_devon_token(token: str, settings: PresenceSettings) -> Optional[Dict[str, Any]]:
    """The DEVON access token's claims, or None when it does not verify."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
    if payload.get("type") != "access":
        return None
    if not str(payload.get("sub") or "").strip():
        return None
    return payload

def _require_devon_token(request: Request, settings: PresenceSettings) -> Dict[str, Any]:
    """The verified DEVON claims, or 401. Shared by every authenticated route.

    Written once rather than per route because two copies of an auth check are
    one edit away from disagreeing, and the cheaper copy is always the one that
    gets relaxed.
    """
    header = request.headers.get("authorization") or ""
    scheme, _, raw_token = header.partition(" ")
    if scheme.lower() != "bearer" or not raw_token.strip():
        raise HTTPException(
            status_code=401,
            detail="Authorization: Bearer <DEVON access token> is required",
        )
    payload = decode_devon_token(raw_token.strip(), settings)
    if payload is None:
        raise HTTPException(status_code=401, detail="invalid or expired DEVON access token")
    return payload



#: The longest utterance this endpoint will speak in one call. A chat reply is
#: a few sentences; anything past this is either a runaway generation or a
#: caller using Tee's cloned voice as a free text to speech service, and both
#: cost real Cartesia credits.
TTS_TEXT_LIMIT = 1200


class SpeakRequest(BaseModel):
    """Text to say in DEVON's own voice.

    No voice field, deliberately, and there will not be one. The voice is
    CARTESIA_VOICE_ID on this service, which is Tee's own clone or a character
    voiced under recorded consent. A caller-chosen voice id would turn this into
    a rented-persona endpoint, which the estate's standing rule refuses outright
    and which has no exception path.
    """

    text: str = Field(min_length=1, max_length=TTS_TEXT_LIMIT)


class LiveKitTokenRequest(BaseModel):
    """The room is the presence session id the server issued in ``ready``.

    There is no identity field. The participant identity is always the
    DEVON user id from the verified token: a caller-chosen identity would let
    one signed-in user evict another from the room by claiming their name.
    """

    room: str = Field(min_length=1, max_length=128)


def create_app(
    settings: Optional[PresenceSettings] = None,
    *,
    primary: Optional[TokenStreamer] = None,
    fallback: Optional[TokenStreamer] = None,
    speech: Optional[SpeechSynthesizer] = None,
    pacer: Optional[Pacer] = None,
    breaker: Optional[CircuitBreaker] = None,
) -> FastAPI:
    """Build the service. Injected pieces override what the settings would build."""
    settings = settings if settings is not None else PresenceSettings.from_env()
    primary = primary if primary is not None else build_streamer(settings.PRESENCE_INFERENCE, settings)
    if primary is None:
        raise PresenceConfigError("PRESENCE_INFERENCE resolved to no streamer")
    if fallback is None:
        fallback = build_streamer(settings.PRESENCE_FALLBACK_INFERENCE, settings)
    breaker = breaker if breaker is not None else CircuitBreaker(
        ttft_threshold_ms=settings.PRESENCE_TTFT_THRESHOLD_MS
    )
    router = InferenceRouter(
        primary,
        fallback,
        breaker=breaker,
        ttft_threshold_ms=settings.PRESENCE_TTFT_THRESHOLD_MS,
    )
    runtime = Runtime(
        settings=settings,
        router=router,
        speech=speech if speech is not None else build_speech(settings),
        pacer=pacer if pacer is not None else RealTimePacer(),
    )

    app = FastAPI(title="DEVON Presence", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.PRESENCE_CORS_ORIGINS),
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.state.runtime = runtime

    @app.get("/health")
    async def health() -> Dict[str, Any]:
        return {
            "status": "ok",
            "service": SERVICE_NAME,
            "inference": runtime.router.primary.name,
            "fallback": runtime.router.fallback_name,
            "speech": runtime.speech.name,
            # Readable because it is otherwise unknowable from outside, and it
            # fails silently: the chat's POST /tts is the first cross origin
            # request the web app makes to this service, so a localhost only
            # list means the browser discards a 200 and DEVON goes quiet with
            # no error anywhere. A critic measured that shape on 2026-09-09.
            # These are the estate's own public web origins, not a secret.
            "cors_origins": list(settings.PRESENCE_CORS_ORIGINS),
            "livekit_configured": settings.livekit_configured,
            "audio_over_websocket": runtime.send_audio_over_websocket,
            "breaker": runtime.router.breaker.snapshot(),
        }

    @app.post("/livekit/token")
    async def livekit_token(request: Request, body: LiveKitTokenRequest) -> Dict[str, Any]:
        payload = _require_devon_token(request, settings)
        if not settings.livekit_configured:
            raise HTTPException(
                status_code=503,
                detail=(
                    "LiveKit is not configured on this service: set LIVEKIT_URL, "
                    "LIVEKIT_API_KEY and LIVEKIT_API_SECRET. Until then audio is "
                    "delivered over the presence WebSocket."
                ),
            )
        identity = str(payload["sub"])
        owner = runtime.sessions.get(body.room)
        if owner is None or owner != identity:
            raise HTTPException(
                status_code=403,
                detail=(
                    "the room must be the session_id of a presence session this user "
                    "holds open; open the WebSocket first and use the id from ready"
                ),
            )
        now = time.time()
        token = mint_livekit_token(
            settings.LIVEKIT_API_KEY,
            settings.LIVEKIT_API_SECRET,
            identity,
            body.room,
            ttl_seconds=DEFAULT_TTL_SECONDS,
            now=now,
        )
        expires_at = datetime.fromtimestamp(int(now) + DEFAULT_TTL_SECONDS, tz=timezone.utc)
        return {
            "token": token,
            "url": settings.LIVEKIT_URL,
            "room": body.room,
            "identity": identity,
            "expires_at": expires_at.isoformat().replace("+00:00", "Z"),
        }

    @app.post("/tts")
    async def tts(request: Request, body: SpeakRequest) -> StreamingResponse:
        """Speak one piece of text in DEVON's voice, as newline delimited JSON.

        WHY THIS EXISTS. Tee opened /devon on 2026-09-09 and DEVON answered in a
        stock female browser voice. DevonChat was calling window.speechSynthesis
        and taking whatever the machine had installed, so the estate had two
        surfaces speaking as DEVON with two different voices and only one of
        them owned. The standing rule is voice and identity owned, never rented,
        and it carries no exception path, so the browser voice comes out and the
        chat borrows the clone the presence service already holds.

        The wire format is the same audio message the socket sends, so the
        browser decodes and schedules it with the same tested code rather than a
        second copy that can drift. Face frames are not emitted: the chat has no
        avatar to drive, and sending them would be bytes nobody reads.
        """
        _require_devon_token(request, settings)
        text = body.text.strip()
        if not text:
            raise HTTPException(status_code=422, detail="nothing to say")

        turn = f"tts-{uuid.uuid4().hex}"

        async def lines() -> AsyncIterator[bytes]:
            seq = 0
            async for chunk in runtime.speech.synthesize(text, turn):
                if chunk.kind != CHUNK_AUDIO or not chunk.pcm:
                    continue
                seq += 1
                message = audio_message(turn, seq, chunk.at_ms, chunk.pcm)
                yield (json.dumps(message, separators=(",", ":")) + "\n").encode("utf-8")

        return StreamingResponse(
            lines(),
            media_type="application/x-ndjson",
            # The voice is named on the response rather than in the body so a
            # reader can tell a real clone from the mock adapter's silence
            # without decoding a single chunk. Silence and a working voice are
            # otherwise indistinguishable from the client side.
            headers={"X-Devon-Speech": runtime.speech.name},
        )

    @app.websocket("/ws/presence")
    async def presence_ws(ws: WebSocket) -> None:
        await ws.accept()

        async def send_json(message: Dict[str, Any]) -> None:
            await ws.send_text(json.dumps(message, allow_nan=False))

        # -- hello, within the timeout -------------------------------------
        try:
            raw = await asyncio.wait_for(ws.receive_text(), timeout=HELLO_TIMEOUT_SECONDS)
            hello = parse_client_message(raw)
            if hello["t"] != "hello":
                raise ProtocolError("first message must be hello")
        except WebSocketDisconnect:
            return
        except asyncio.TimeoutError:
            await send_json(error_message(ERR_MALFORMED, "no hello within the timeout"))
            await ws.close(code=CLOSE_MALFORMED)
            return
        except ProtocolError as exc:
            await send_json(error_message(ERR_MALFORMED, f"malformed hello: {exc}"))
            await ws.close(code=CLOSE_MALFORMED)
            return

        payload = decode_devon_token(str(hello.get("token") or ""), settings)
        if payload is None:
            await send_json(
                error_message(ERR_UNAUTHENTICATED, "sign in first: valid DEVON access token required")
            )
            await ws.close(code=CLOSE_UNAUTHENTICATED)
            return

        session = PresenceSession(
            session_id=uuid.uuid4().hex,
            user_id=str(payload["sub"]),
            router=runtime.router,
            speech=runtime.speech,
            send=send_json,
            window_ms=settings.PRESENCE_WINDOW_MS,
            pacer=runtime.pacer,
            send_audio=runtime.send_audio_over_websocket,
        )
        await send_json(
            ready_message(
                session_id=session.session_id,
                speech=runtime.speech.name,
                inference=runtime.router.primary.name,
                fallback=runtime.router.fallback_name,
                livekit_configured=settings.livekit_configured,
                livekit_url=settings.LIVEKIT_URL or None,
            )
        )
        runtime.sessions[session.session_id] = session.user_id
        await session.open()

        # -- conversation ----------------------------------------------------
        try:
            while not session.closed:
                raw = await ws.receive_text()
                try:
                    message = parse_client_message(raw)
                except ProtocolError as exc:
                    await session.emit(error_message(exc.code, str(exc)))
                    continue
                kind = message["t"]
                if kind == "say":
                    await session.begin_turn(message["turn_id"], message["text"])
                elif kind == "interrupt":
                    await session.interrupt(message["turn_id"], float(message["at_ms"]))
                elif kind == "render":
                    session.report_render(
                        message["turn_id"], float(message["behind_ms"]), float(message["fps"])
                    )
                elif kind == "ping":
                    await session.emit(pong_message(message["at_ms"]))
                elif kind == "hello":
                    await session.emit(error_message(ERR_MALFORMED, "already authenticated"))
        except WebSocketDisconnect:
            pass
        finally:
            runtime.sessions.pop(session.session_id, None)
            await session.close()
            try:
                await ws.close()
            except (RuntimeError, WebSocketDisconnect):
                pass

    return app


app = create_app()

"""LiveKit join tokens, minted with PyJWT directly.

There is no LiveKit SDK in ``requirements.txt`` and none is needed for
this: a LiveKit access token is a plain HS256 JWT signed with the API
secret. The claim layout below is the one LiveKit documents at
docs.livekit.io/frontends/authentication/tokens (decoded example: ``exp``,
``iss`` set to the API key, ``sub`` set to the participant identity,
``nbf``, ``video`` with ``room`` and ``roomJoin``, plus ``metadata``) and
the one its own Python ``TokenVerifier`` checks with
``jwt.decode(token, key=api_secret, issuer=api_key, algorithms=["HS256"])``.

Verification note, recorded honestly: docs.livekit.io is blocked by this
build environment's egress proxy, so the page was read through the
Context7 documentation index of that site on 2026-09-08, not fetched
directly. The layout matched the spec that named it. Whether a token
minted here is accepted by a live LiveKit server was not tested in this
build; that needs LIVEKIT_* credentials and a room, which is the next
gate.

The optional ``name`` claim is the participant's display name. ``metadata``
is not set: nothing in this service has anything to put there yet, and an
empty claim is a claim a reader has to wonder about.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

import jwt

LIVEKIT_ALGORITHM = "HS256"
DEFAULT_TTL_SECONDS = 3600


def mint_livekit_token(
    api_key: str,
    api_secret: str,
    identity: str,
    room: str,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    name: str = "",
    can_publish: bool = True,
    can_subscribe: bool = True,
    now: Optional[float] = None,
) -> str:
    """Return a signed LiveKit join token for ``identity`` in ``room``.

    ``now`` is epoch seconds and is injectable so a test can pin ``nbf``
    and ``exp`` instead of reading the wall clock back.
    """
    if not api_key or not api_secret:
        raise ValueError("LIVEKIT_API_KEY and LIVEKIT_API_SECRET are both required to mint")
    if not identity or not identity.strip():
        raise ValueError("identity must be a non empty string")
    if not room or not room.strip():
        raise ValueError("room must be a non empty string")
    if ttl_seconds <= 0:
        raise ValueError("ttl_seconds must be greater than zero")
    issued = int(time.time() if now is None else now)
    claims: Dict[str, Any] = {
        "iss": api_key,
        "sub": identity,
        "nbf": issued,
        "exp": issued + int(ttl_seconds),
        "name": name or "",
        "video": {
            "room": room,
            "roomJoin": True,
            "canPublish": bool(can_publish),
            "canSubscribe": bool(can_subscribe),
        },
    }
    return jwt.encode(claims, api_secret, algorithm=LIVEKIT_ALGORITHM)


def decode_livekit_token(token: str, api_key: str, api_secret: str) -> Dict[str, Any]:
    """Verify signature, issuer and time claims; return the claims. For tests."""
    return jwt.decode(
        token,
        api_secret,
        algorithms=[LIVEKIT_ALGORITHM],
        issuer=api_key,
        options={"require": ["exp", "iss", "sub", "nbf"]},
    )

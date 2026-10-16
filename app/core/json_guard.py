"""Refuse a JSON body that carries a lone UTF-16 surrogate.

A body such as a string holding the escape for U+D800 is legal JSON and decodes to a Python str
that cannot be encoded as UTF-8. It then fails later, in the validation error
echo or in the database driver, and the client sees a 500. Found 2026-10-14
and reproduced on /auth/login and /auth/register. The fix is to name the
problem once, at the door, and answer 422 like any other bad input.

A well formed pair (a high surrogate escape directly followed by a low one)
is an ordinary astral character and passes untouched.
"""

from __future__ import annotations

import json
import re
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

# Any escape in the surrogate block. Bodies without one skip the parse.
_SURROGATE_ESCAPE = re.compile(rb"\\[uU][dD][89a-fA-F][0-9a-fA-F]{2}")
MAX_CHECKED_BYTES = 8 * 1024 * 1024
_MESSAGE = "request body contains an unpaired surrogate character"


def _has_lone_surrogate(value: Any) -> bool:
    if isinstance(value, str):
        return any(0xD800 <= ord(ch) <= 0xDFFF for ch in value)
    if isinstance(value, dict):
        return any(_has_lone_surrogate(k) or _has_lone_surrogate(v) for k, v in value.items())
    if isinstance(value, list):
        return any(_has_lone_surrogate(v) for v in value)
    return False


def _may_hold_surrogate(body: bytes) -> bool:
    """The escape text, or any byte pattern a decoder could turn into one.

    json.loads decodes bytes with surrogatepass, so a lone surrogate can arrive
    as raw UTF-8 bytes, or in a UTF-16 or UTF-32 body where the escape text is
    wide. Plain ASCII with no NUL cannot carry one without the escape text.
    """
    return bool(_SURROGATE_ESCAPE.search(body)) or not body.isascii() or b"\x00" in body


def body_has_lone_surrogate(body: bytes) -> bool:
    if not _may_hold_surrogate(body):
        return False
    try:
        return _has_lone_surrogate(json.loads(body))
    except (ValueError, RecursionError):
        # Not valid JSON: the route's own decoder reports that.
        return False


class LoneSurrogateGuard:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] not in ("POST", "PUT", "PATCH"):
            await self.app(scope, receive, send)
            return
        content_type = b""
        for name, value in scope.get("headers", []):
            if name == b"content-type":
                content_type = value.lower()
                break
        if b"json" not in content_type:
            await self.app(scope, receive, send)
            return

        chunks: list[Message] = []
        body = bytearray()
        while True:
            message = await receive()
            chunks.append(message)
            if message["type"] != "http.request":
                break
            body.extend(message.get("body", b""))
            if not message.get("more_body", False):
                break

        if len(body) <= MAX_CHECKED_BYTES and body_has_lone_surrogate(bytes(body)):
            payload = json.dumps({
                "detail": _MESSAGE,
                "error": {"code": "validation_error", "message": _MESSAGE, "status": 422},
            }).encode()
            await send({"type": "http.response.start", "status": 422,
                        "headers": [(b"content-type", b"application/json"),
                                    (b"content-length", str(len(payload)).encode())]})
            await send({"type": "http.response.body", "body": payload})
            return

        replay = iter(chunks)

        async def replayed() -> Message:
            try:
                return next(replay)
            except StopIteration:
                return await receive()

        await self.app(scope, replayed, send)

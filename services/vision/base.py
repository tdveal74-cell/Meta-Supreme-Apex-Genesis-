"""Vision contracts, kept deliberately separate from the text completion path.

`services/intelligence/providers/base.py` is byte mirrored into
`deploy/soul/services/intelligence/providers/base.py` and `test_deploy_soul.py`
asserts the two files are identical, so every edit there spends a production
Vercel build of devon-soul on a service that gains nothing from vision. That is
the first reason this package exists instead of a wider `ChatMessage`.

The second reason was measured rather than reasoned about on 2026-09-16.
`ChatMessage(role="user", content=[{...}])` is accepted today with no error,
and both HTTP providers then put that list on the wire untranslated, producing
byte identical JSON for two vendors whose block schemas differ. Widening the
type alone therefore buys a contract that works for one vendor and 400s the
other, while `MockProvider` raises AttributeError and `AgentTurn` quietly
stringifies the blocks. A separate path has to translate per vendor, and
`test_devon_vision_path.py` pins that the two bodies differ.

Nothing here carries an image back out. `VisionResponse.text` is a string, so
the rest of DEVON keeps handling text and never a binary.
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Optional

from services.intelligence.providers.base import ProviderError, TokenUsage

# The four types a phone or a screenshot actually produces. Anything else is
# refused at construction rather than sent and charged for.
ALLOWED_MEDIA_TYPES = ("image/jpeg", "image/png", "image/webp", "image/gif")

# A ceiling, not a guess at the vendor limit. It exists because the 017 usage
# ledger charges a vision call at the text token rate and has no column for an
# image, so an unbounded frame is an unbounded under charge against the daily
# cap. Bounding the bytes bounds the error. See the open ruling in
# docs/devon/SYS_OPS_devon-gets-eyes_v1_2026-09-16h.md.
DEFAULT_MAX_IMAGE_BYTES = 5 * 1024 * 1024


class VisionUnsupportedError(ProviderError):
    """The configured backend cannot accept an image. Never retryable."""


@dataclass(frozen=True)
class ImageSource:
    """One image, validated at construction and never mutated afterwards.

    Built only through `from_bytes`. The digest is what an approval card shows
    Tee, since a card can prove which bytes are about to leave the host but
    cannot render a thumbnail of them.
    """

    media_type: str
    data: bytes
    digest: str
    byte_count: int

    @classmethod
    def from_bytes(
        cls,
        data: bytes,
        *,
        media_type: str,
        max_bytes: int = DEFAULT_MAX_IMAGE_BYTES,
    ) -> "ImageSource":
        if not isinstance(data, (bytes, bytearray)):
            raise ValueError("image data must be bytes")
        if not data:
            raise ValueError("image data is empty")
        normalised = str(media_type or "").strip().lower()
        if normalised not in ALLOWED_MEDIA_TYPES:
            raise ValueError(
                f"unsupported media type {normalised or 'unknown'}; "
                f"allowed: {', '.join(ALLOWED_MEDIA_TYPES)}"
            )
        if len(data) > max_bytes:
            raise ValueError(
                f"image is {len(data)} bytes and the ceiling is {max_bytes}"
            )
        payload = bytes(data)
        return cls(
            media_type=normalised,
            data=payload,
            digest=hashlib.sha256(payload).hexdigest(),
            byte_count=len(payload),
        )


@dataclass
class VisionRequest:
    """One image and one question about it."""

    image: ImageSource
    prompt: str
    model: Optional[str] = None
    max_tokens: int = 700
    metadata: Dict[str, object] = field(default_factory=dict)


@dataclass
class VisionResponse:
    """Text out. Never an image, never a block list."""

    text: str
    usage: TokenUsage
    model: str
    provider: str
    latency_ms: int = 0


class VisionProvider(ABC):
    """One method. There is no second, unmetered door into a paid call."""

    name: str = "abstract"
    supports_images: bool = True

    def __init__(self, *, default_model: str, timeout_seconds: float = 60.0) -> None:
        self.default_model = default_model
        self.timeout_seconds = timeout_seconds

    def resolve_model(self, request: VisionRequest) -> str:
        return request.model or self.default_model

    @abstractmethod
    async def describe(self, request: VisionRequest) -> VisionResponse:
        """Describe the image. Raises a ProviderError subclass on failure."""

"""Vision backends. Each one translates the SAME VisionRequest differently.

That difference is the whole point of this module. On the text path a block
list is handed to both vendors untranslated and the two bodies come out byte
identical, which is why widening `ChatMessage` would have shipped a contract
that works for one vendor and 400s the other.
`test_devon_vision_path.py::test_the_two_vendors_get_different_bodies` pins
that these two do not make that mistake.

`LocalVisionProvider` exists before anything needs it. The seam that lets a
frame stay on the host has to be in place on day one, or it becomes a retrofit
nobody does.
"""

from __future__ import annotations

import base64
import time
from typing import Optional

import httpx

from services.intelligence.providers.anthropic_provider import _error_detail
from services.intelligence.providers.base import (
    ProviderAuthError,
    ProviderBillingError,
    ProviderConfigError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderServerError,
    ProviderTimeoutError,
    TokenUsage,
    billing_message,
    billing_refusal,
)
from services.vision.base import (
    VisionProvider,
    VisionRequest,
    VisionResponse,
    VisionUnsupportedError,
)

ANTHROPIC_VISION_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
OPENAI_VISION_URL = "https://api.openai.com/v1/chat/completions"


def _raise_for_status(response: httpx.Response, *, provider: str, vendor: str) -> None:
    """One mapping for every vision backend.

    Copied behaviour, not copied code: this maps onto the same seven error
    classes as `OpenAIProvider._raise_for_status`, and
    `test_devon_vision_path.py::test_the_error_mapping_matches_the_text_path`
    drives both with the same status codes so the two cannot drift silently.
    """
    if response.status_code < 400:
        return
    detail = _error_detail(response)
    # Funding first. An empty account picks its own status code and two of
    # them collide with a real condition, so this cannot sit after the 401
    # and 429 branches. See ProviderBillingError.
    reason = billing_refusal(response.status_code, detail)
    if reason:
        raise ProviderBillingError(
            billing_message(vendor, response.status_code, detail, reason),
            provider=provider,
        )
    if response.status_code == 401:
        raise ProviderAuthError(
            f"{vendor} authentication failed: {detail}", provider=provider
        )
    if response.status_code == 429:
        raise ProviderRateLimitError(f"{vendor} rate limit: {detail}", provider=provider)
    if response.status_code >= 500:
        raise ProviderServerError(
            f"{vendor} server error {response.status_code}: {detail}", provider=provider
        )
    raise ProviderResponseError(
        f"{vendor} rejected the request ({response.status_code}): {detail}",
        provider=provider,
    )


class MockVisionProvider(VisionProvider):
    """Offline default. Reports the bytes it was handed and calls nothing."""

    name = "mock"

    def __init__(self, *, default_model: str = "mock-vision", **_: object) -> None:
        super().__init__(default_model=default_model)

    async def describe(self, request: VisionRequest) -> VisionResponse:
        image = request.image
        text = (
            f"[mock vision] {image.byte_count} bytes of {image.media_type}, "
            f"sha256 {image.digest[:12]}, asked: {request.prompt.strip()[:120]}"
        )
        return VisionResponse(
            text=text,
            usage=TokenUsage(input_tokens=0, output_tokens=0),
            model=self.resolve_model(request),
            provider=self.name,
            latency_ms=0,
        )


class _HttpVisionProvider(VisionProvider):
    """Shared transport, timing and error handling. Subclasses own the body."""

    vendor = "vendor"
    api_url = ""
    requires_key = True

    def __init__(
        self,
        *,
        api_key: str = "",
        default_model: str,
        timeout_seconds: float = 60.0,
        transport: Optional[httpx.AsyncBaseTransport] = None,
        api_url: Optional[str] = None,
    ) -> None:
        if self.requires_key and not api_key:
            raise ProviderConfigError(
                f"{self.vendor} vision needs an API key. Set one, or set "
                "VISION_PROVIDER to 'mock' for offline development.",
                provider=self.name,
            )
        super().__init__(default_model=default_model, timeout_seconds=timeout_seconds)
        self._api_key = api_key
        self._transport = transport
        if api_url:
            self.api_url = api_url

    def _body(self, request: VisionRequest) -> dict:
        raise NotImplementedError

    def _headers(self) -> dict:
        raise NotImplementedError

    def _read(self, data: dict, request: VisionRequest) -> VisionResponse:
        raise NotImplementedError

    async def describe(self, request: VisionRequest) -> VisionResponse:
        started = time.monotonic()
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds, transport=self._transport
            ) as client:
                response = await client.post(
                    self.api_url, json=self._body(request), headers=self._headers()
                )
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                f"{self.vendor} vision timed out after {self.timeout_seconds}s",
                provider=self.name,
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderServerError(
                f"Network error calling {self.vendor} vision: {exc}", provider=self.name
            ) from exc

        _raise_for_status(response, provider=self.name, vendor=self.vendor)
        answer = self._read(response.json(), request)
        answer.latency_ms = int((time.monotonic() - started) * 1000)
        return answer


class AnthropicVisionProvider(_HttpVisionProvider):
    """Anthropic Messages API. Image is a base64 source block."""

    name = "anthropic"
    vendor = "Anthropic"
    api_url = ANTHROPIC_VISION_URL

    def __init__(self, *, default_model: str = "claude-sonnet-5", **kwargs: object) -> None:
        super().__init__(default_model=default_model, **kwargs)  # type: ignore[arg-type]

    def _headers(self) -> dict:
        return {
            "x-api-key": self._api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "Content-Type": "application/json",
        }

    def _body(self, request: VisionRequest) -> dict:
        image = request.image
        return {
            "model": self.resolve_model(request),
            "max_tokens": request.max_tokens,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": image.media_type,
                                "data": base64.b64encode(image.data).decode("ascii"),
                            },
                        },
                        {"type": "text", "text": request.prompt},
                    ],
                }
            ],
        }

    def _read(self, data: dict, request: VisionRequest) -> VisionResponse:
        parts = [
            block.get("text", "")
            for block in data.get("content", [])
            if block.get("type") == "text"
        ]
        text = "".join(parts).strip()
        if not text:
            raise ProviderResponseError(
                "Anthropic vision answered with no text block", provider=self.name
            )
        usage = data.get("usage", {})
        return VisionResponse(
            text=text,
            usage=TokenUsage(
                input_tokens=int(usage.get("input_tokens", 0)),
                output_tokens=int(usage.get("output_tokens", 0)),
            ),
            model=data.get("model", self.resolve_model(request)),
            provider=self.name,
        )


class OpenAIVisionProvider(_HttpVisionProvider):
    """OpenAI compatible Chat Completions. Image is a data URI."""

    name = "openai"
    vendor = "OpenAI"
    api_url = OPENAI_VISION_URL

    def __init__(self, *, default_model: str = "gpt-5.2", **kwargs: object) -> None:
        super().__init__(default_model=default_model, **kwargs)  # type: ignore[arg-type]

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def _body(self, request: VisionRequest) -> dict:
        image = request.image
        encoded = base64.b64encode(image.data).decode("ascii")
        return {
            "model": self.resolve_model(request),
            "max_completion_tokens": request.max_tokens,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": request.prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{image.media_type};base64,{encoded}"
                            },
                        },
                    ],
                }
            ],
        }

    def _read(self, data: dict, request: VisionRequest) -> VisionResponse:
        choices = data.get("choices") or []
        if not choices:
            raise ProviderResponseError(
                f"{self.vendor} vision returned no choices", provider=self.name
            )
        message = choices[0].get("message") or {}
        text = str(message.get("content") or "").strip()
        if not text:
            raise ProviderResponseError(
                f"{self.vendor} vision answered with an empty description",
                provider=self.name,
            )
        usage = data.get("usage", {})
        return VisionResponse(
            text=text,
            usage=TokenUsage(
                input_tokens=int(usage.get("prompt_tokens", 0)),
                output_tokens=int(usage.get("completion_tokens", 0)),
            ),
            model=data.get("model", self.resolve_model(request)),
            provider=self.name,
        )


class LocalVisionProvider(OpenAIVisionProvider):
    """An OpenAI compatible server on the host. No key, no frame leaving the box.

    The seam, built before it is needed. Swapping to it is one setting, so the
    privacy answer never depends on a refactor nobody has time for.
    """

    name = "local"
    vendor = "Local"
    requires_key = False
    api_url = "http://127.0.0.1:8080/v1/chat/completions"


def create_vision_provider(
    name: str,
    *,
    api_key: str = "",
    default_model: str = "",
    timeout_seconds: float = 60.0,
    transport: Optional[httpx.AsyncBaseTransport] = None,
    api_url: Optional[str] = None,
) -> VisionProvider:
    """Build a backend by name. Refuses the text only lane by name, loudly."""
    key = str(name or "").strip().lower()

    if key == "cerebras":
        from services.intelligence.providers.cerebras_provider import SUPPORTS_IMAGES

        raise VisionUnsupportedError(
            "Cerebras serves text models and SUPPORTS_IMAGES is "
            f"{SUPPORTS_IMAGES}; it cannot read a frame. Choose anthropic, "
            "openai, local or mock.",
            provider="cerebras",
        )

    if key in ("", "mock"):
        return MockVisionProvider(default_model=default_model or "mock-vision")

    shared: dict = {"timeout_seconds": timeout_seconds, "transport": transport}
    if api_url:
        shared["api_url"] = api_url

    if key == "anthropic":
        return AnthropicVisionProvider(
            api_key=api_key, **({"default_model": default_model} if default_model else {}), **shared
        )
    if key == "openai":
        return OpenAIVisionProvider(
            api_key=api_key, **({"default_model": default_model} if default_model else {}), **shared
        )
    if key == "local":
        return LocalVisionProvider(
            **({"default_model": default_model} if default_model else {"default_model": "local-vision"}),
            **shared,
        )

    raise VisionUnsupportedError(
        f"unknown vision provider '{name}'. Choose anthropic, openai, local or mock.",
        provider=key or "unknown",
    )

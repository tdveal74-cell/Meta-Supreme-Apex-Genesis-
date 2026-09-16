"""The vision lane is metered and capped like every other paid call.

The first test here exists because a factory that forgets its wrapper loses
the cap silently, and this estate has already shipped that bug once in
`apps/presence/inference.py`. So the wrapper is asserted, not assumed.

The last test pins a KNOWN under count rather than papering over it. The 017
ledger has no column for an image, so a frame is charged at whatever token
counts the vendor reports and at the text rate. If a vendor prices image input
above that, this account is under charged against its daily cap by that factor.
`VISION_MAX_IMAGE_BYTES` bounds how wrong it can get. The day someone adds a
cost column, this test is what says the behaviour changed.
"""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.core.tenant_context import bind_tenant, current_tenant_id, reset_tenant
from app.services.intelligence import get_vision_provider
from app.services.provider_usage import (
    MeteredVisionProvider,
    ProviderSpendCapExceeded,
    read_usage,
    record_usage,
)
from services.vision.base import ImageSource, VisionRequest, VisionResponse
from services.vision.providers import MockVisionProvider

PNG = b"\x89PNG\r\n\x1a\n" + b"pixels" * 8


def _request() -> VisionRequest:
    return VisionRequest(
        image=ImageSource.from_bytes(PNG, media_type="image/png"),
        prompt="what is on this screen",
    )


class _Counting(MockVisionProvider):
    def __init__(self, *, input_tokens: int = 0, output_tokens: int = 0) -> None:
        super().__init__()
        self.calls = 0
        self._input = input_tokens
        self._output = output_tokens

    async def describe(self, request: VisionRequest) -> VisionResponse:
        self.calls += 1
        answer = await super().describe(request)
        answer.usage.input_tokens = self._input
        answer.usage.output_tokens = self._output
        return answer


def test_the_factory_does_not_lose_its_wrapper():
    provider = get_vision_provider()
    assert isinstance(provider, MeteredVisionProvider)
    assert hasattr(provider, "inner")
    # There is no second, unmetered door the way MeteredProvider._complete_once is.
    assert not hasattr(provider, "_describe_once")


async def test_an_account_at_the_cap_is_refused_before_the_frame_is_sent(db_session):
    token = bind_tenant("vision-capped-tenant")
    original = settings.PROVIDER_DAILY_TOKEN_CAP
    try:
        settings.PROVIDER_DAILY_TOKEN_CAP = 100
        await record_usage(current_tenant_id(), input_tokens=100, output_tokens=0)

        inner = _Counting()
        metered = MeteredVisionProvider(inner)

        with pytest.raises(ProviderSpendCapExceeded):
            await metered.describe(_request())

        assert inner.calls == 0, "a capped account still reached the vision backend"
    finally:
        settings.PROVIDER_DAILY_TOKEN_CAP = original
        reset_tenant(token)


async def test_the_ledger_records_exactly_what_the_backend_reported(db_session):
    token = bind_tenant("vision-ledger-tenant")
    original = settings.PROVIDER_DAILY_TOKEN_CAP
    try:
        settings.PROVIDER_DAILY_TOKEN_CAP = 0  # disabled, so only the record is tested
        before = await read_usage(current_tenant_id())

        inner = _Counting(input_tokens=1200, output_tokens=64)
        metered = MeteredVisionProvider(inner)
        answer = await metered.describe(_request())

        assert inner.calls == 1
        assert answer.usage.input_tokens == 1200

        after = await read_usage(current_tenant_id())
        assert after.input_tokens - before.input_tokens == 1200
        assert after.output_tokens - before.output_tokens == 64
    finally:
        settings.PROVIDER_DAILY_TOKEN_CAP = original
        reset_tenant(token)


async def test_the_image_is_charged_at_the_text_rate_and_that_is_bounded(db_session):
    """A known, bounded under count, pinned so a fix is visible as a change.

    The ledger has six columns and none of them is cost, model, provider or
    modality, so a frame and a paragraph of the same token count spend the same
    against the cap. The byte ceiling is what bounds the error.
    """
    token = bind_tenant("vision-rate-tenant")
    original = settings.PROVIDER_DAILY_TOKEN_CAP
    try:
        settings.PROVIDER_DAILY_TOKEN_CAP = 0
        before = await read_usage(current_tenant_id())

        inner = _Counting(input_tokens=500, output_tokens=10)
        await MeteredVisionProvider(inner).describe(_request())

        after = await read_usage(current_tenant_id())
        # No multiplier is applied anywhere. This is the under count, stated.
        assert after.total_tokens - before.total_tokens == 510
        assert settings.VISION_MAX_IMAGE_BYTES == 5 * 1024 * 1024
    finally:
        settings.PROVIDER_DAILY_TOKEN_CAP = original
        reset_tenant(token)

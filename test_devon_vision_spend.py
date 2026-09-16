"""The vision lane is metered and capped like every other paid call.

The first test here exists because a factory that forgets its wrapper loses
the cap silently, and this estate has already shipped that bug once in
`apps/presence/inference.py`. So the wrapper is asserted, not assumed.

The tests after it cover what used to be a pinned under count and is now a
named ratio. The 017 ledger has no column for cost or modality, so charging a
frame at whatever the vendor reported silently assumed a vendor prices an image
token like a text one. `VISION_INPUT_TOKEN_WEIGHT` makes that assumption
explicit: 1.0 is parity and is what ships, a vendor that prices image input
higher takes its real ratio, and below parity is refused twice over.
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
    weighted_vision_input,
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


async def test_the_weight_defaults_to_parity_so_the_shipped_number_is_unchanged(db_session):
    """1.0 records exactly what the vendor said, which is what shipped.

    A deployment that never sets the weight must get the old behaviour to the
    token, or this change would silently re-price every existing account.
    """
    token = bind_tenant("vision-parity-tenant")
    original_cap = settings.PROVIDER_DAILY_TOKEN_CAP
    original_weight = settings.VISION_INPUT_TOKEN_WEIGHT
    try:
        settings.PROVIDER_DAILY_TOKEN_CAP = 0
        settings.VISION_INPUT_TOKEN_WEIGHT = 1.0
        before = await read_usage(current_tenant_id())

        inner = _Counting(input_tokens=500, output_tokens=10)
        await MeteredVisionProvider(inner).describe(_request())

        after = await read_usage(current_tenant_id())
        assert after.total_tokens - before.total_tokens == 510
    finally:
        settings.PROVIDER_DAILY_TOKEN_CAP = original_cap
        settings.VISION_INPUT_TOKEN_WEIGHT = original_weight
        reset_tenant(token)


async def test_a_weight_above_parity_charges_the_input_and_leaves_the_output(db_session):
    """The weight prices image INPUT. Output is text and is charged as text.

    Weighting the output too would be a second, unearned multiplier on tokens
    the vendor already prices at its text rate.
    """
    token = bind_tenant("vision-weighted-tenant")
    original_cap = settings.PROVIDER_DAILY_TOKEN_CAP
    original_weight = settings.VISION_INPUT_TOKEN_WEIGHT
    try:
        settings.PROVIDER_DAILY_TOKEN_CAP = 0
        settings.VISION_INPUT_TOKEN_WEIGHT = 3.0
        before = await read_usage(current_tenant_id())

        inner = _Counting(input_tokens=500, output_tokens=10)
        answer = await MeteredVisionProvider(inner).describe(_request())

        after = await read_usage(current_tenant_id())
        assert after.input_tokens - before.input_tokens == 1500
        assert after.output_tokens - before.output_tokens == 10

        # The RESPONSE still reports the vendor's own number. The weight is an
        # accounting ratio, not a claim about what the vendor said, and a
        # receipt that inflated it would be a lie about the call.
        assert answer.usage.input_tokens == 500
    finally:
        settings.PROVIDER_DAILY_TOKEN_CAP = original_cap
        settings.VISION_INPUT_TOKEN_WEIGHT = original_weight
        reset_tenant(token)


def test_a_fractional_weight_rounds_up_so_rounding_never_favours_the_account():
    original = settings.VISION_INPUT_TOKEN_WEIGHT
    try:
        settings.VISION_INPUT_TOKEN_WEIGHT = 1.5
        assert weighted_vision_input(101) == 152  # 151.5 rounded up, not down
        settings.VISION_INPUT_TOKEN_WEIGHT = 1.01
        assert weighted_vision_input(1) == 2  # 1.01 is still more than one token
    finally:
        settings.VISION_INPUT_TOKEN_WEIGHT = original


def test_a_weight_below_parity_still_charges_the_full_vendor_number():
    """The second guard. The config validator refuses such a weight at start up.

    This one covers a value set after start up or patched in a test: the
    recorder floors at what the vendor reported rather than trusting it.
    """
    original = settings.VISION_INPUT_TOKEN_WEIGHT
    try:
        settings.VISION_INPUT_TOKEN_WEIGHT = 0.25
        assert weighted_vision_input(400) == 400
        settings.VISION_INPUT_TOKEN_WEIGHT = 0
        assert weighted_vision_input(400) == 400
    finally:
        settings.VISION_INPUT_TOKEN_WEIGHT = original


def test_the_config_refuses_a_weight_that_under_charges():
    """The first guard, at start up, so a bad deployment never boots quiet."""
    from app.core.config import Settings

    with pytest.raises(ValueError, match="VISION_INPUT_TOKEN_WEIGHT"):
        Settings(VISION_INPUT_TOKEN_WEIGHT=0.5)

    # Parity and above are accepted.
    assert Settings(VISION_INPUT_TOKEN_WEIGHT=1.0).VISION_INPUT_TOKEN_WEIGHT == 1.0
    assert Settings(VISION_INPUT_TOKEN_WEIGHT=2.5).VISION_INPUT_TOKEN_WEIGHT == 2.5


def test_the_vision_inbox_is_in_the_checkout_for_the_root_to_point_at():
    """Ruled 2026-09-16: a dedicated inbox, not the working tree.

    The directory is tracked through its README so a fresh checkout has
    somewhere for `VISION_IMAGE_ROOT` to point, and the frames inside it are
    not, because a frame is whatever was on a screen and this repo is public.
    """
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parent
    inbox = root / "var" / "vision-inbox"
    assert inbox.is_dir(), "var/vision-inbox is missing; VISION_IMAGE_ROOT has no target"
    assert (inbox / "README.md").is_file()

    ignored = subprocess.run(
        ["git", "check-ignore", "var/vision-inbox/anything.png"],
        cwd=root, capture_output=True, text=True,
    )
    assert ignored.returncode == 0, "a frame dropped in the inbox would be committable"

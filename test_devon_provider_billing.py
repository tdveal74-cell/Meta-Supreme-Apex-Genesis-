"""An empty account is its own failure, and it is never retryable.

Tee ruled on 2026-09-16, on an inline card: fund neither Anthropic nor
OpenRouter, and make the failure loud instead. Both lanes run on Cerebras and a
free OpenRouter endpoint today, so funding buys nothing; what cost a morning was
not the missing money, it was that nobody could tell what the error meant.

OS 29 had been detecting policy changes and assessing none of them since the VPS
cutover. n8n reported it as "Bad request - please check your parameters", which
is n8n's wording for any vendor 400. The real body read "Your credit balance is
too low to access the Anthropic API". The key authenticated. A different model id
returned the identical error, which is what ruled out the model string before
anyone touched the credential.

The fix is a classifier, not a better sentence, because the status codes collide
with real conditions:

    Anthropic  400  reads as a parameter bug
    OpenAI     429  reads as a busy endpoint, and WAS RETRIED
    OpenRouter 402  is unambiguous and was still lumped in with bad requests

The OpenAI case is the one that was actually broken rather than merely unclear:
an unfunded account looked exactly like a rate limited one, so the lane retried
a balance that does not refill.
"""

from __future__ import annotations

import httpx
import pytest

from services.intelligence.providers.anthropic_provider import AnthropicProvider
from services.intelligence.providers.base import (
    ProviderBillingError,
    ProviderRateLimitError,
    ProviderResponseError,
    billing_message,
    billing_refusal,
)
from services.intelligence.providers.openai_provider import OpenAIProvider
from services.vision.providers import _raise_for_status as vision_raise

ANTHROPIC_EMPTY = "Your credit balance is too low to access the Anthropic API"


def _response(status: int, body: dict | None = None) -> httpx.Response:
    return httpx.Response(
        status,
        json=body if body is not None else {},
        request=httpx.Request("POST", "https://vendor.example/v1"),
    )


# ---------------------------------------------------------------------------
# The classifier, on its own
# ---------------------------------------------------------------------------

def test_402_is_billing_on_the_status_alone():
    """Payment Required means this and nothing else, body or no body."""
    assert billing_refusal(402, "") is not None
    assert billing_refusal(402, "anything at all") is not None


def test_each_vendor_s_own_wording_is_recognised():
    assert billing_refusal(400, ANTHROPIC_EMPTY) is not None
    assert billing_refusal(429, '{"error":{"type":"insufficient_quota"}}') is not None
    assert billing_refusal(429, "You exceeded your current quota") is not None
    assert billing_refusal(402, "Insufficient credits") is not None


def test_a_real_rate_limit_is_not_billing():
    """The narrowness is the point: a busy endpoint must stay retryable.

    Matching "quota" alone would swallow this, and a lane that stops retrying a
    genuine rate limit is a worse bug than the one being fixed.
    """
    assert billing_refusal(429, "Rate limit reached for requests") is None
    assert billing_refusal(429, "Too many requests, slow down") is None
    assert billing_refusal(429, "rate_limit_exceeded: free-models-per-day") is None


def test_a_real_parameter_error_is_not_billing():
    assert billing_refusal(400, "model: field required") is None
    assert billing_refusal(400, "messages[0].content must be a string") is None
    assert billing_refusal(404, "model not found") is None


def test_the_message_carries_the_vendor_s_own_words_and_the_misleading_status():
    """The whole failure was a status code read as something else.

    So the message has to carry BOTH the number that misled and the sentence
    that explains it, and it has to quote the vendor rather than paraphrase.
    """
    text = billing_message("Anthropic", 400, ANTHROPIC_EMPTY, "reason here")
    assert "400" in text
    assert ANTHROPIC_EMPTY in text
    assert "not because the request was wrong" in text
    assert "Retrying will not help" in text
    assert "Fund the Anthropic account" in text


# ---------------------------------------------------------------------------
# Every backend maps it the same way
# ---------------------------------------------------------------------------

def test_the_anthropic_400_that_cost_a_morning():
    provider = AnthropicProvider(api_key="k")
    with pytest.raises(ProviderBillingError) as exc:
        provider._raise_for_status(_response(400, {"error": {"message": ANTHROPIC_EMPTY}}))
    assert exc.value.retryable is False
    assert ANTHROPIC_EMPTY in str(exc.value)


def test_the_openai_429_was_retried_and_must_not_be():
    """The behaviour change, asserted as a change.

    OpenAI answers an unfunded account with 429, which mapped to
    ProviderRateLimitError(retryable=True). This pins that it no longer does.
    """
    provider = OpenAIProvider(api_key="k")
    body = {"error": {"type": "insufficient_quota", "message": "You exceeded your current quota"}}
    with pytest.raises(ProviderBillingError) as exc:
        provider._raise_for_status(_response(429, body))
    assert exc.value.retryable is False
    assert not isinstance(exc.value, ProviderRateLimitError)


def test_a_genuine_openai_429_is_still_a_retryable_rate_limit():
    provider = OpenAIProvider(api_key="k")
    with pytest.raises(ProviderRateLimitError) as exc:
        provider._raise_for_status(
            _response(429, {"error": {"message": "Rate limit reached for requests"}})
        )
    assert exc.value.retryable is True


def test_a_genuine_400_is_still_a_response_error():
    provider = AnthropicProvider(api_key="k")
    with pytest.raises(ProviderResponseError) as exc:
        provider._raise_for_status(_response(400, {"error": {"message": "model: field required"}}))
    assert not isinstance(exc.value, ProviderBillingError)


def test_the_vision_path_maps_it_the_same_as_the_text_path():
    """These two mappings are copied behaviour, not copied code.

    `test_devon_vision_path.py::test_the_error_mapping_matches_the_text_path`
    already drives both with the same status codes so they cannot drift. The
    billing branch is held to the same rule.
    """
    with pytest.raises(ProviderBillingError) as exc:
        vision_raise(
            _response(402, {"error": {"message": "Insufficient credits"}}),
            provider="openrouter",
            vendor="OpenRouter",
        )
    assert exc.value.retryable is False
    assert exc.value.provider == "openrouter"

    with pytest.raises(ProviderRateLimitError):
        vision_raise(
            _response(429, {"error": {"message": "rate_limit_exceeded: free-models-per-day"}}),
            provider="openrouter",
            vendor="OpenRouter",
        )


def test_billing_is_never_retryable_whatever_the_status():
    """A retryable empty balance is a lane burning its own schedule."""
    for status in (400, 402, 403, 429):
        error = ProviderBillingError(
            billing_message("Vendor", status, "no money", "reason"), provider="p"
        )
        assert error.retryable is False

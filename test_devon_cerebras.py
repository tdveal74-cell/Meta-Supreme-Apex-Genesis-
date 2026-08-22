"""
Tests for the Cerebras lane and capture enrichment.

Every test injects an httpx MockTransport. Nothing here reaches the network, so
the suite runs offline and a green run is not evidence that a key works.
"""

import json

import httpx
import pytest

from services.devon.areas import canonical_labels
from services.intelligence.enrichment import (
    DECLINE_TOKEN,
    MAX_SUMMARY_CHARS,
    enrich_capture,
    refuse_image_enrichment,
)
from services.intelligence.providers import (
    CerebrasProvider,
    ChatMessage,
    CompletionRequest,
    MockProvider,
    ProviderConfigError,
    ProviderRateLimitError,
    RateLimiter,
    create_provider,
)
from services.intelligence.providers.cerebras_provider import (
    CEREBRAS_API_URL,
    DEFAULT_MODEL,
)


def cerebras_response(content: str, prompt_tokens: int = 30, completion_tokens: int = 20):
    """A Cerebras shaped Chat Completions body."""
    return {
        "model": DEFAULT_MODEL,
        "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
    }


def transport_returning(content: str, capture: dict | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        if capture is not None:
            capture["url"] = str(request.url)
            capture["headers"] = dict(request.headers)
            capture["body"] = json.loads(request.content)
        return httpx.Response(200, json=cerebras_response(content))

    return httpx.MockTransport(handler)


def make_provider(content: str, capture: dict | None = None, **kwargs) -> CerebrasProvider:
    return CerebrasProvider(
        api_key="test-key",
        transport=transport_returning(content, capture),
        **kwargs,
    )


# -- provider wiring ---------------------------------------------------------


def test_a_missing_key_fails_loudly_and_names_the_right_variable():
    with pytest.raises(ProviderConfigError) as excinfo:
        CerebrasProvider(api_key="")
    message = str(excinfo.value)
    assert "CEREBRAS_API_KEY" in message
    assert "OPENAI_API_KEY" not in message
    assert "never in the vault" in message


def test_the_factory_builds_a_cerebras_provider():
    provider = create_provider("cerebras", cerebras_api_key="k")
    assert isinstance(provider, CerebrasProvider)
    assert provider.name == "cerebras"
    assert provider.default_model == DEFAULT_MODEL


def test_the_factory_still_refuses_an_unknown_provider():
    with pytest.raises(ProviderConfigError, match="cerebras"):
        create_provider("wat")


def test_the_factory_tightens_the_timeout_for_this_lane():
    """Measured latency is 42ms. A 60s wait would mask a dead endpoint."""
    provider = create_provider("cerebras", cerebras_api_key="k", timeout_seconds=60.0)
    assert provider.timeout_seconds <= 30.0


async def test_it_calls_the_cerebras_endpoint_with_a_bearer_key():
    capture: dict = {}
    provider = make_provider('{"area": "Podcast", "summary": "ok"}', capture)
    await provider.complete(
        CompletionRequest(messages=[ChatMessage(role="user", content="hello")])
    )
    assert capture["url"] == CEREBRAS_API_URL
    assert capture["headers"]["authorization"] == "Bearer test-key"
    assert capture["body"]["model"] == DEFAULT_MODEL


async def test_the_openai_provider_default_url_is_untouched():
    """Subclassing must not have moved the base class's endpoint."""
    from services.intelligence.providers.openai_provider import OpenAIProvider

    assert OpenAIProvider.api_url == "https://api.openai.com/v1/chat/completions"
    assert CerebrasProvider.api_url == CEREBRAS_API_URL


# -- rate limiting -----------------------------------------------------------


def test_the_limiter_refuses_at_the_minute_boundary():
    limiter = RateLimiter(per_minute=5)
    for _ in range(5):
        limiter.check(now=100.0)
        limiter.record(now=100.0)
    with pytest.raises(ProviderRateLimitError, match="5 requests per minute"):
        limiter.check(now=100.0)


def test_the_minute_window_slides():
    limiter = RateLimiter(per_minute=5, per_hour=1000, per_day=10000)
    for _ in range(5):
        limiter.record(now=100.0)
    limiter.check(now=200.0)


def test_the_limiter_refuses_at_the_hour_boundary():
    limiter = RateLimiter(per_minute=1000, per_hour=150)
    for index in range(150):
        limiter.record(now=100.0 + index * 0.001)
    with pytest.raises(ProviderRateLimitError, match="per hour"):
        limiter.check(now=200.0)


def test_the_limiter_refuses_on_the_daily_token_allowance():
    limiter = RateLimiter(tokens_per_day=1000)
    limiter.record(tokens=1000, now=100.0)
    with pytest.raises(ProviderRateLimitError, match="daily token allowance"):
        limiter.check(now=200.0)


def test_the_snapshot_reports_spend_rather_than_guessing():
    limiter = RateLimiter()
    limiter.record(tokens=50, now=100.0)
    snapshot = limiter.snapshot(now=100.0)
    assert snapshot["last_minute"] == 1
    assert snapshot["tokens_today"] == 50
    assert snapshot["limits"]["per_minute"] == 5


async def test_the_provider_records_usage_against_the_limiter():
    limiter = RateLimiter()
    provider = make_provider('{"area": "Systems", "summary": "ok"}', limiter=limiter)
    await provider.complete(
        CompletionRequest(messages=[ChatMessage(role="user", content="hi")])
    )
    snapshot = limiter.snapshot()
    assert snapshot["last_minute"] == 1
    assert snapshot["tokens_today"] == 50


async def test_an_exhausted_limiter_refuses_before_the_call():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json=cerebras_response('{"area": "Systems"}'))

    limiter = RateLimiter(per_minute=0)
    provider = CerebrasProvider(
        api_key="k", transport=httpx.MockTransport(handler), limiter=limiter, max_retries=0
    )
    with pytest.raises(ProviderRateLimitError):
        await provider.complete(
            CompletionRequest(messages=[ChatMessage(role="user", content="hi")])
        )
    assert calls["n"] == 0, "the limiter must refuse before any HTTP call"


# -- enrichment: the contract that matters -----------------------------------


async def test_a_valid_suggested_area_is_honoured():
    provider = make_provider('{"area": "Podcast", "summary": "A TSWS cold open note."}')
    result = await enrich_capture("vespera cold open idea", provider)
    assert result.area_label == "Podcast"
    assert result.area_provenance == "supplied and validated"
    assert result.summary == "A TSWS cold open note."
    assert not result.declined


async def test_an_invented_area_is_discarded_and_keywords_take_over():
    """A model supplied Area is never trusted."""
    provider = make_provider('{"area": "Business", "summary": "about the channel"}')
    result = await enrich_capture("the tqo channel monetization plan", provider)
    assert result.model_suggested_area == "Business"
    assert result.area_label == "TQO"
    assert "rejected" in result.area_provenance
    assert "keyword fallback" in result.area_provenance


async def test_an_invented_area_with_no_keyword_signal_declines():
    provider = make_provider('{"area": "Business", "summary": "unclear"}')
    result = await enrich_capture("qqq zzz nothing here", provider)
    assert result.area is None
    assert result.declined


async def test_the_model_is_allowed_to_decline():
    """Given a bare identifier the live lane returned empty. That is correct."""
    provider = make_provider(f'{{"area": "{DECLINE_TOKEN}", "summary": ""}}')
    result = await enrich_capture("8f14e45fceea167a5a36dedd4bea2543", provider)
    assert result.model_suggested_area == DECLINE_TOKEN
    assert result.area is None
    assert result.declined
    assert "model declined" in result.area_provenance


async def test_a_decline_still_lets_keywords_answer():
    provider = make_provider(f'{{"area": "{DECLINE_TOKEN}", "summary": ""}}')
    result = await enrich_capture("the n8n workflow and airtable base", provider)
    assert result.area_label == "Systems"
    assert "model declined" in result.area_provenance


async def test_unparseable_output_does_not_invent_a_tag():
    provider = make_provider("I think this is probably about the podcast, mate")
    result = await enrich_capture("vespera and auren episode", provider)
    assert result.model_suggested_area is None
    assert result.area_label == "Podcast"
    assert "keyword" in result.area_provenance.lower()


async def test_a_provider_failure_degrades_rather_than_losing_the_capture():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": {"message": "down"}})

    provider = CerebrasProvider(
        api_key="k", transport=httpx.MockTransport(handler), max_retries=0
    )
    result = await enrich_capture("the tqo channel plan", provider)
    assert result.error is not None
    assert result.area_label == "TQO"
    assert "provider failed" in result.area_provenance


async def test_empty_input_declines_without_calling_the_provider():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json=cerebras_response("{}"))

    provider = CerebrasProvider(api_key="k", transport=httpx.MockTransport(handler))
    result = await enrich_capture("   ", provider)
    assert result.declined
    assert calls["n"] == 0


async def test_the_summary_is_bounded():
    long_summary = "x" * 500
    provider = make_provider(json.dumps({"area": "Systems", "summary": long_summary}))
    result = await enrich_capture("n8n workflow", provider)
    assert len(result.summary) <= MAX_SUMMARY_CHARS


async def test_the_prompt_lists_exactly_the_nine_areas():
    capture: dict = {}
    provider = make_provider('{"area": "Systems", "summary": "s"}', capture)
    await enrich_capture("n8n workflow", provider)
    system = capture["body"]["messages"][0]["content"]
    for label in canonical_labels():
        assert label in system
    assert "Business" not in system
    assert "Never invent an Area" in system


async def test_enrichment_works_with_any_provider_not_just_cerebras():
    """The abstraction is the point. Cerebras is a configuration choice."""
    provider = MockProvider(responder=lambda req: '{"area": "Health", "summary": "gym"}')
    result = await enrich_capture("a note", provider)
    assert result.area_label == "Health"
    assert result.provider == "mock"


def test_image_enrichment_is_refused_with_the_reason_stated():
    result = refuse_image_enrichment("IMG_2550")
    assert result.declined
    assert result.area is None
    assert "text only" in result.area_provenance


async def test_the_result_serialises_for_logging():
    provider = make_provider('{"area": "Money", "summary": "an invoice"}')
    result = await enrich_capture("the invoice and budget", provider)
    payload = result.to_dict()
    assert payload["area"] == "Money"
    assert payload["provider"] == "cerebras"
    assert payload["tokens"] == 50


# -- the call site must thread every key the factory accepts -----------------


def test_the_factory_accepts_a_key_for_every_supported_provider():
    """A regression guard for the gap this test was written after.

    `cerebras` was added to the factory and to config, and the application call
    site was not updated to pass its key, so DEFAULT_AI_PROVIDER=cerebras built a
    provider with an empty key and raised. Adding a provider without threading
    its key through is silent until someone flips the setting in production.

    This asserts the shape rather than the specific names, so the next provider
    added is covered without anyone remembering to extend the test.
    """
    import inspect

    from services.intelligence.providers.factory import (
        SUPPORTED_PROVIDERS,
    )
    from services.intelligence.providers.factory import (
        create_provider as factory_create,
    )

    signature = inspect.signature(factory_create)
    key_params = {p for p in signature.parameters if p.endswith("_api_key")}

    # Every provider that is not the offline mock needs a credential parameter.
    needs_key = [p for p in SUPPORTED_PROVIDERS if p != "mock"]
    for provider_name in needs_key:
        expected = f"{provider_name}_api_key"
        assert expected in key_params, (
            f"factory has no '{expected}' parameter for supported provider "
            f"'{provider_name}'"
        )


def test_the_application_call_site_passes_every_factory_key():
    """Read the call site and confirm no credential parameter was left behind."""
    import inspect
    import pathlib
    import re

    from services.intelligence.providers.factory import create_provider as factory_create

    key_params = {
        p for p in inspect.signature(factory_create).parameters if p.endswith("_api_key")
    }

    source = pathlib.Path("app/services/intelligence.py").read_text(encoding="utf-8")
    calls = re.findall(r"create_provider\((.*?)\n    \)", source, re.DOTALL)
    assert calls, "no create_provider call found in app/services/intelligence.py"

    for call in calls:
        for key in key_params:
            assert key in call, f"call site does not pass '{key}': {call[:120]}"

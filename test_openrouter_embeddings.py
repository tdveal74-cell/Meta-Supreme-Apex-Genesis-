"""Transport contract and fail-closed tests; no live account or billing."""

import json
from types import SimpleNamespace

import httpx
import pytest

from services.intelligence.providers.base import (
    ProviderAuthError,
    ProviderBillingError,
    ProviderConfigError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderServerError,
)
from services.intelligence.providers.embeddings import create_embedding_provider
from services.intelligence.providers.openrouter_embeddings import MODEL, OpenRouterEmbeddingProvider


def payload(n=1):
    return {
        "model": MODEL,
        "data": [{"index": i, "embedding": [0.5 + i / 10] * 1536} for i in reversed(range(n))],
        "usage": {"prompt_tokens": 12},
    }


async def test_openrouter_request_model_dimensions_order_and_identity():
    def respond(request):
        assert str(request.url) == "https://openrouter.ai/api/v1/embeddings"
        assert request.headers["Authorization"] == "Bearer test-only"
        body = json.loads(request.content)
        assert body["model"] == MODEL
        assert body["dimensions"] == 1536
        assert body["input"] == ["first", "second"]
        assert body["encoding_format"] == "float"
        assert body["provider"]["allow_fallbacks"] is False
        return httpx.Response(200, json=payload(2))

    p = OpenRouterEmbeddingProvider(api_key="test-only", transport=httpx.MockTransport(respond))
    result = await p.embed(["first", "second"])
    assert result.provider == "openrouter" and result.model == MODEL
    assert result.input_tokens == 12
    assert result.vectors[0][0] == 0.5 and result.vectors[1][0] == 0.6


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p.update(model="different/model"),
        lambda p: p.update(data=[]),
        lambda p: p["data"][0].update(index=1),
        lambda p: p["data"][0].update(index=True),
        lambda p: p["data"][0].update(embedding=[1.0] * 1024),
        lambda p: p["data"][0].update(embedding=[0.0] * 1536),
        lambda p: p["data"][0]["embedding"].__setitem__(0, "1"),
        lambda p: p["data"][0]["embedding"].__setitem__(0, True),
        lambda p: p.update(usage={"prompt_tokens": -1}),
        lambda p: p.update(usage={"prompt_tokens": 0}),
        lambda p: p.pop("usage"),
        lambda p: p.update(usage={}),
    ],
)
async def test_openrouter_rejects_malformed_batch(mutate):
    data = payload()
    mutate(data)
    p = OpenRouterEmbeddingProvider(
        api_key="test-only", transport=httpx.MockTransport(lambda _: httpx.Response(200, json=data))
    )
    with pytest.raises(ProviderResponseError):
        await p.embed(["text"])


@pytest.mark.parametrize(
    "body",
    [
        "not json",
        '{"model":"openai/text-embedding-3-small","data":[{"index":0,"embedding":[NaN]}]}',
        "null",
    ],
)
async def test_openrouter_rejects_invalid_json(body):
    p = OpenRouterEmbeddingProvider(
        api_key="test-only", transport=httpx.MockTransport(lambda _: httpx.Response(200, text=body))
    )
    with pytest.raises(ProviderResponseError):
        await p.embed(["text"])


@pytest.mark.parametrize(
    "status,error",
    [
        (401, ProviderAuthError),
        (403, ProviderAuthError),
        (402, ProviderBillingError),
        (400, ProviderResponseError),
        (429, ProviderRateLimitError),
        (503, ProviderServerError),
    ],
)
async def test_openrouter_errors_preserve_type_without_leaking_body(status, error):
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(status, text="private-key-and-input-must-not-appear")

    p = OpenRouterEmbeddingProvider(
        api_key="test-only", max_retries=0, transport=httpx.MockTransport(respond)
    )
    with pytest.raises(error) as raised:
        await p.embed(["text"])
    assert "private-key" not in str(raised.value)
    assert len(calls) == 1


async def test_openrouter_funding_never_retries():
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(429, text='{"error":{"code":"insufficient_quota"}}')

    p = OpenRouterEmbeddingProvider(api_key="test-only", transport=httpx.MockTransport(respond))
    with pytest.raises(ProviderBillingError):
        await p.embed(["text"])
    assert len(calls) == 1


def test_factory_requires_its_own_key_and_pinned_model():
    with pytest.raises(ProviderConfigError):
        create_embedding_provider("openrouter", openai_api_key="wrong-provider")
    with pytest.raises(ProviderConfigError):
        create_embedding_provider("openrouter", openrouter_api_key="test-only", model="other/model")
    p = create_embedding_provider("openrouter", openrouter_api_key="test-only")
    assert p.name == "openrouter" and p.default_model == MODEL


@pytest.mark.parametrize("module", ["app.services.knowledge", "services.knowledge.pipeline"])
def test_both_ingestion_paths_use_openrouter_key(monkeypatch, module):
    import importlib

    service = importlib.import_module(module)
    monkeypatch.setattr(
        service,
        "settings",
        SimpleNamespace(
            EMBEDDING_PROVIDER="openrouter",
            OPENROUTER_API_KEY="test-only",
            DEFAULT_AI_PROVIDER="cerebras",
        ),
    )
    assert service._embedding_provider().name == "openrouter"

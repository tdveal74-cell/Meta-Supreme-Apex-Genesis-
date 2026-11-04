"""Gemini request contract and call-site wiring, offline with injected HTTP."""

import json
from pathlib import Path

import httpx
import pytest

from services.intelligence.providers import (
    ChatMessage,
    CompletionRequest,
    GeminiProvider,
    ProviderAuthError,
    ProviderConfigError,
    ProviderResponseError,
    create_completion_provider,
    create_provider,
)
from services.intelligence.providers.gemini_provider import DEFAULT_MODEL, GEMINI_API_URL


def test_factory_and_completion_factory_require_gemini_key():
    for factory in (create_provider, create_completion_provider):
        with pytest.raises(ProviderConfigError, match="GEMINI_API_KEY"):
            factory("gemini", cerebras_api_key="legacy-key", openai_api_key="other-key")
        provider = factory(" Gemini ", gemini_api_key="google-key")
        assert isinstance(provider, GeminiProvider)
        assert provider.name == "gemini"
        assert provider.default_model == DEFAULT_MODEL
        assert provider.api_url == GEMINI_API_URL


async def test_gemini_uses_its_own_endpoint_and_max_tokens_contract():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={
            "model": "gemini-3.8-flash",
            "choices": [{"message": {"content": '{"ok": true}'}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 9, "completion_tokens": 4},
        })

    provider = GeminiProvider(api_key="google-key", transport=httpx.MockTransport(handler))
    response = await provider.complete(CompletionRequest(
        system="Return JSON.", messages=[ChatMessage(role="user", content="Check this")],
        max_tokens=321, temperature=0.25, json_mode=True, stop_sequences=["END"],
    ))
    assert seen["url"] == GEMINI_API_URL
    assert seen["auth"] == "Bearer google-key"
    assert seen["body"] == {
        "model": DEFAULT_MODEL, "max_tokens": 321, "reasoning_effort": "low",
        "messages": [{"role": "system", "content": "Return JSON."}, {"role": "user", "content": "Check this"}],
        "response_format": {"type": "json_object"}, "stop": ["END"],
    }
    assert "max_completion_tokens" not in seen["body"]
    assert response.provider == "gemini"
    assert response.model == DEFAULT_MODEL
    assert response.text == '{"ok": true}'
    assert response.usage.total_tokens == 13
    assert response.finish_reason == "stop"


@pytest.mark.parametrize("status,error", [(401, ProviderAuthError), (403, ProviderResponseError)])
async def test_auth_and_permission_refusals_never_retry(status, error):
    calls = []

    def handler(request):
        calls.append(request)
        # Google's error bodies can be a list, unlike OpenAI's object body.
        return httpx.Response(status, json=[{"error": {"message": "Permission denied"}}])

    provider = GeminiProvider(api_key="invalid", max_retries=3, transport=httpx.MockTransport(handler))
    with pytest.raises(error) as caught:
        await provider.complete(CompletionRequest(messages=[ChatMessage(role="user", content="hi")]))
    assert caught.value.provider == "gemini"
    assert len(calls) == 1


async def test_missing_choices_is_a_failure_not_an_empty_success():
    provider = GeminiProvider(api_key="k", max_retries=0, transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={"choices": []})
    ))
    with pytest.raises(ProviderResponseError):
        await provider.complete(CompletionRequest(messages=[ChatMessage(role="user", content="hi")]))


def test_api_and_enrichment_build_metered_gemini_with_configured_model(monkeypatch):
    from app.services import intelligence
    from app.services.provider_usage import MeteredProvider

    monkeypatch.setattr(intelligence.settings, "DEFAULT_AI_PROVIDER", "gemini")
    monkeypatch.setattr(intelligence.settings, "ENRICHMENT_PROVIDER", "gemini")
    monkeypatch.setattr(intelligence.settings, "GEMINI_API_KEY", "google-key")
    monkeypatch.setattr(intelligence.settings, "GEMINI_MODEL", "gemini-custom")
    monkeypatch.setattr(intelligence.settings, "AI_MODEL", None)
    intelligence.get_provider.cache_clear()
    intelligence.get_enrichment_provider.cache_clear()
    try:
        for provider in (intelligence.get_provider(), intelligence.get_enrichment_provider()):
            assert isinstance(provider, MeteredProvider)
            assert isinstance(provider.inner, GeminiProvider)
            assert provider.inner._api_key == "google-key"
            assert provider.default_model == "gemini-custom"
    finally:
        intelligence.get_provider.cache_clear()
        intelligence.get_enrichment_provider.cache_clear()


def test_presence_accepts_gemini_and_passes_key_and_model():
    from apps.presence.inference import build_streamer
    from apps.presence.settings import PresenceSettings

    settings = PresenceSettings.from_env({
        "PRESENCE_INFERENCE": "gemini", "GEMINI_API_KEY": "google-key",
        "GEMINI_MODEL": "gemini-custom", "ENVIRONMENT": "test",
    })
    streamer = build_streamer(settings.PRESENCE_INFERENCE, settings)
    assert isinstance(streamer._provider, GeminiProvider)
    assert streamer._provider._api_key == "google-key"
    assert streamer._provider.default_model == "gemini-custom"
    with pytest.raises(ProviderConfigError, match="GEMINI_API_KEY"):
        build_streamer("gemini", PresenceSettings())


def test_knowledge_completion_gemini_does_not_rewire_embeddings(monkeypatch):
    from app.services.provider_usage import MeteredProvider
    from services.intelligence.providers.embeddings import resolve_embedding_provider_name
    from services.knowledge import pipeline

    monkeypatch.setattr(pipeline.settings, "DEFAULT_AI_PROVIDER", "gemini")
    monkeypatch.setattr(pipeline.settings, "GEMINI_API_KEY", "google-key")
    monkeypatch.setattr(pipeline.settings, "GEMINI_MODEL", "gemini-custom")
    monkeypatch.setattr(pipeline.settings, "EMBEDDING_PROVIDER", "mock")
    provider = pipeline._completion_provider()
    assert isinstance(provider, MeteredProvider)
    assert isinstance(provider.inner, GeminiProvider)
    assert provider.default_model == "gemini-custom"
    assert resolve_embedding_provider_name(pipeline.settings) == "mock"


def test_bootstrap_selects_gemini_and_leaves_offline_templates_offline():
    root = Path(__file__).resolve().parent
    bootstrap = (root / "start-devon.sh").read_text()
    assert "DEFAULT_AI_PROVIDER=gemini" in bootstrap
    assert "ENRICHMENT_PROVIDER=gemini" in bootstrap
    assert "GEMINI_API_KEY=" in bootstrap
    assert "DEFAULT_AI_PROVIDER=cerebras" not in bootstrap
    template = (root / "infrastructure/docker/.env.prod.example").read_text()
    assert "DEFAULT_AI_PROVIDER=mock" in template
    assert "GEMINI_MODEL=gemini-3.8-flash" in template


@pytest.mark.parametrize("model", ["gemini-3.8-flash", "gemini-3.8-flash-preview"])
def test_gemini_38_request_omits_deprecated_sampling(model):
    provider = GeminiProvider(api_key="test-key", default_model=model)
    body = provider._request_body(CompletionRequest(messages=[ChatMessage(role="user", content="test")], temperature=0.25))
    assert "temperature" not in body
    assert body["reasoning_effort"] == "low"
    assert "top_p" not in body and "top_k" not in body
    assert body["max_tokens"] == 1024


def test_other_gemini_models_retain_their_own_sampling_contract():
    provider = GeminiProvider(api_key="test-key", default_model="gemini-2.5-flash")
    body = provider._request_body(CompletionRequest(messages=[ChatMessage(role="user", content="test")], temperature=0.25))
    assert body["temperature"] == 0.25


@pytest.mark.parametrize("response_body", [[], None, {"choices": "wrong"}, {"choices": [None]}, {"usage": []}])
async def test_malformed_gemini_success_is_a_typed_nonretryable_failure(response_body):
    provider = GeminiProvider(api_key="test-key", max_retries=0, transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json=response_body)
    ))
    with pytest.raises(ProviderResponseError) as caught:
        await provider.complete(CompletionRequest(messages=[ChatMessage(role="user", content="test")]))
    assert caught.value.provider == "gemini"
    assert not caught.value.retryable


def test_presence_accepts_gemini_fallback_without_replacing_existing_primary():
    from apps.presence.settings import PresenceSettings
    settings = PresenceSettings.from_env({"PRESENCE_INFERENCE": "cerebras", "PRESENCE_FALLBACK_INFERENCE": "gemini", "ENVIRONMENT": "test"})
    assert settings.PRESENCE_INFERENCE == "cerebras"
    assert settings.PRESENCE_FALLBACK_INFERENCE == "gemini"


@pytest.mark.parametrize("body", [
    {"choices": [{}]},
    {"choices": [{"message": {"content": 42}}]},
    {"choices": [{"message": {"content": []}}]},
    {"choices": [{"message": {"content": "ok"}}], "usage": {"prompt_tokens": -9, "completion_tokens": 4}},
    {"choices": [{"message": {"content": "ok"}}], "usage": {"prompt_tokens": True, "completion_tokens": 4}},
    {"choices": [{"message": {"content": "ok"}}], "usage": {"prompt_tokens": "9", "completion_tokens": 4}},
    {"choices": [{"message": {"content": "ok"}}], "usage": {"prompt_tokens": 9, "completion_tokens": -4}},
    {"choices": [{"message": {"content": "ok"}}], "usage": {"prompt_tokens": 9}},
    {"choices": [{"message": {"content": "ok"}}]},
])
async def test_invalid_gemini_content_and_usage_cannot_be_success(body):
    provider = GeminiProvider(api_key="test-key", max_retries=0, transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json=body)
    ))
    with pytest.raises(ProviderResponseError) as caught:
        await provider.complete(CompletionRequest(messages=[ChatMessage(role="user", content="test")]))
    assert caught.value.provider == "gemini"
    assert not caught.value.retryable


async def test_empty_filtered_content_keeps_a_typed_measured_result():
    provider = GeminiProvider(api_key="test-key", max_retries=0, transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={
            "choices": [{"message": {"content": ""}, "finish_reason": "content_filter"}],
            "usage": {"prompt_tokens": 9, "completion_tokens": 0},
        })
    ))
    result = await provider.complete(CompletionRequest(messages=[ChatMessage(role="user", content="test")]))
    assert result.text == "" and result.finish_reason == "content_filter"
    assert result.usage.total_tokens == 9



def test_bootstrap_pinecone_key_block_stays_independent(tmp_path):
    import os
    import re
    import subprocess
    import sys
    source = (Path(__file__).parent / "start-devon.sh").read_text()
    block = re.search(r'"\$VENV_PY" - "\$PINECONE_INPUT" <<\'PYEOF\'\n(.*?)\nPYEOF', source, re.S).group(1)
    env = dict(os.environ)
    env.pop("GEMINI_BOOTSTRAP_KEY", None)
    (tmp_path / ".env").write_text("PINECONE_API_KEY=\nGEMINI_API_KEY=unchanged\n")
    subprocess.run([sys.executable, "-c", block, "fake-pinecone-key"], cwd=tmp_path, env=env, check=True)
    assert (tmp_path / ".env").read_text() == "PINECONE_API_KEY=fake-pinecone-key\nGEMINI_API_KEY=unchanged\n"


def test_bootstrap_gemini_key_block_reads_private_environment_only(tmp_path):
    import os
    import re
    import subprocess
    import sys
    source = (Path(__file__).parent / "start-devon.sh").read_text()
    block = re.search(r'GEMINI_BOOTSTRAP_KEY="\$GEMINI_INPUT" "\$VENV_PY" - <<\'PYEOF\'\n(.*?)\nPYEOF', source, re.S).group(1)
    (tmp_path / ".env").write_text("PINECONE_API_KEY=unchanged\nGEMINI_API_KEY=\n")
    subprocess.run([sys.executable, "-c", block], cwd=tmp_path,
                   env={**os.environ, "GEMINI_BOOTSTRAP_KEY": "fake-gemini-key"}, check=True)
    assert (tmp_path / ".env").read_text() == "PINECONE_API_KEY=unchanged\nGEMINI_API_KEY=fake-gemini-key\n"
    assert '"$VENV_PY" - "$GEMINI_INPUT"' not in source

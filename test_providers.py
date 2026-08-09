"""AI provider abstraction tests — mock determinism, HTTP shaping, retries."""

import json

import httpx
import pytest

from services.intelligence.providers import (
    AnthropicProvider,
    ChatMessage,
    CompletionRequest,
    MockProvider,
    OpenAIProvider,
    ProviderAuthError,
    ProviderConfigError,
    ProviderRateLimitError,
    create_provider,
    extract_json,
)

# ---------------------------------------------------------------------------
# Mock provider
# ---------------------------------------------------------------------------

async def test_mock_provider_is_deterministic():
    provider = MockProvider()
    request = CompletionRequest(
        messages=[ChatMessage(role="user", content="Evaluate the launch plan")]
    )
    first = await provider.complete(request)
    second = await provider.complete(request)
    assert first.text == second.text
    assert first.provider == "mock"
    assert first.usage.total_tokens > 0


async def test_mock_provider_honors_json_contract():
    provider = MockProvider()
    request = CompletionRequest(
        system="Reply in JSON.\nREQUIRED_JSON_KEYS: findings, gaps, confidence",
        messages=[ChatMessage(role="user", content="Assess the market")],
        json_mode=True,
    )
    response = await provider.complete(request)
    payload = json.loads(response.text)
    assert set(payload) == {"findings", "gaps", "confidence"}
    assert isinstance(payload["findings"], list)  # plural key → array
    assert isinstance(payload["confidence"], float)


async def test_mock_provider_custom_responder():
    provider = MockProvider(responder=lambda req: '{"answer": 42}')
    response = await provider.complete(
        CompletionRequest(messages=[ChatMessage(role="user", content="?")])
    )
    assert json.loads(response.text) == {"answer": 42}


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def test_factory_builds_each_provider():
    assert create_provider("mock").name == "mock"
    assert create_provider("anthropic", anthropic_api_key="k").name == "anthropic"
    assert create_provider("openai", openai_api_key="k").name == "openai"


def test_factory_rejects_unknown_provider():
    with pytest.raises(ProviderConfigError):
        create_provider("skynet")


def test_factory_requires_api_keys():
    with pytest.raises(ProviderConfigError):
        create_provider("anthropic")
    with pytest.raises(ProviderConfigError):
        create_provider("openai")


# ---------------------------------------------------------------------------
# Anthropic HTTP shaping
# ---------------------------------------------------------------------------

def _anthropic_ok(text: str) -> dict:
    return {
        "content": [{"type": "text", "text": text}],
        "model": "claude-sonnet-5",
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 11, "output_tokens": 7},
    }


async def test_anthropic_request_and_response_mapping():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = request.headers
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=_anthropic_ok("hello"))

    provider = AnthropicProvider(
        api_key="test-key", transport=httpx.MockTransport(handler)
    )
    response = await provider.complete(
        CompletionRequest(
            system="Be brief.",
            messages=[ChatMessage(role="user", content="hi")],
            max_tokens=64,
            json_mode=True,
        )
    )

    assert captured["url"] == "https://api.anthropic.com/v1/messages"
    assert captured["headers"]["x-api-key"] == "test-key"
    assert captured["body"]["model"] == "claude-sonnet-5"
    assert captured["body"]["max_tokens"] == 64
    assert "JSON" in captured["body"]["system"]  # json_mode instruction appended
    assert response.text == "hello"
    assert response.usage.input_tokens == 11
    assert response.usage.output_tokens == 7
    assert response.finish_reason == "end_turn"


async def test_anthropic_auth_error_is_not_retried():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(401, json={"error": {"message": "bad key"}})

    provider = AnthropicProvider(
        api_key="wrong", transport=httpx.MockTransport(handler), max_retries=3
    )
    with pytest.raises(ProviderAuthError):
        await provider.complete(
            CompletionRequest(messages=[ChatMessage(role="user", content="hi")])
        )
    assert calls["n"] == 1  # auth failures never retry


async def test_anthropic_rate_limit_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr(
        AnthropicProvider, "_backoff_seconds", staticmethod(lambda attempt: 0.0)
    )
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(429, json={"error": {"message": "slow down"}})
        return httpx.Response(200, json=_anthropic_ok("recovered"))

    provider = AnthropicProvider(
        api_key="k", transport=httpx.MockTransport(handler), max_retries=2
    )
    response = await provider.complete(
        CompletionRequest(messages=[ChatMessage(role="user", content="hi")])
    )
    assert response.text == "recovered"
    assert calls["n"] == 3


async def test_anthropic_retries_exhausted(monkeypatch):
    monkeypatch.setattr(
        AnthropicProvider, "_backoff_seconds", staticmethod(lambda attempt: 0.0)
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"message": "still limited"}})

    provider = AnthropicProvider(
        api_key="k", transport=httpx.MockTransport(handler), max_retries=1
    )
    with pytest.raises(ProviderRateLimitError):
        await provider.complete(
            CompletionRequest(messages=[ChatMessage(role="user", content="hi")])
        )


# ---------------------------------------------------------------------------
# OpenAI HTTP shaping
# ---------------------------------------------------------------------------

async def test_openai_request_and_response_mapping():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers["Authorization"]
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "model": "gpt-5.2",
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "world"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 5, "completion_tokens": 3},
            },
        )

    provider = OpenAIProvider(api_key="ok-key", transport=httpx.MockTransport(handler))
    response = await provider.complete(
        CompletionRequest(
            system="Be brief.",
            messages=[ChatMessage(role="user", content="hello, reply in JSON")],
            json_mode=True,
        )
    )

    assert captured["url"] == "https://api.openai.com/v1/chat/completions"
    assert captured["auth"] == "Bearer ok-key"
    assert captured["body"]["messages"][0]["role"] == "system"
    assert captured["body"]["response_format"] == {"type": "json_object"}
    assert response.text == "world"
    assert response.usage.total_tokens == 8


# ---------------------------------------------------------------------------
# JSON extraction
# ---------------------------------------------------------------------------

def test_extract_json_handles_fences_and_prose():
    assert extract_json('{"a": 1}') == {"a": 1}
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Here you go:\n{"a": 1}\nHope that helps!') == {"a": 1}


def test_extract_json_rejects_garbage():
    with pytest.raises(ValueError):
        extract_json("no json here at all")

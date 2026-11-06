"""Presence inference must reach the authenticated API's metered provider."""
import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest

from apps.presence import inference
from apps.presence.breaker import InferenceRouter, InferenceUnavailable, TurnMetrics
from apps.presence.inference import MockTokenStreamer
from apps.presence.relay import InferenceRefused, RelayTokenStreamer, access_token
from apps.presence.session import PresenceSession, VirtualPacer
from apps.presence.settings import PresenceConfigError, PresenceSettings
from apps.presence.speech import MockSpeech


def test_real_streamer_never_constructs_an_unmetered_provider(monkeypatch):
    built = []
    def direct_provider(*args, **kwargs):
        built.append(args)
        return SimpleNamespace(name="gemini")
    monkeypatch.setattr(inference, "create_provider", direct_provider)
    settings = SimpleNamespace(
        PRESENCE_API_BASE="https://api.example",
        ANTHROPIC_API_KEY="", OPENAI_API_KEY="", CEREBRAS_API_KEY="",
        GEMINI_API_KEY="fixture-only", GEMINI_MODEL="gemini-3.8-flash",
    )
    inference.build_streamer("gemini", settings)
    assert built == [], "Presence must not bypass the API meter with a direct provider"


@pytest.mark.parametrize("base", [
    "", "http://api.example", "https://user:pass@api.example",
    "https://api.example/path", "https://api.example?secret=x",
    "https://api.example#fragment", "https://api.example:bad",
])
def test_paid_inference_refuses_unsafe_or_missing_api_origin(base):
    with pytest.raises(PresenceConfigError, match="PRESENCE_API_BASE"):
        PresenceSettings.from_env({
            "ENVIRONMENT": "test", "PRESENCE_INFERENCE": "gemini", "PRESENCE_API_BASE": base,
        })


async def test_relay_forwards_only_session_bearer_and_bounded_contract():
    requests = []
    def handle(request):
        requests.append(request)
        return httpx.Response(200, json={
            "provider": "gemini", "text": "Hello there.", "usage_recorded": True,
            "usage": {"input_tokens": 1413, "output_tokens": 192, "total_tokens": 1605},
        })
    relay = RelayTokenStreamer("gemini", "https://api.example/", transport=httpx.MockTransport(handle))
    binding = access_token.set("session-token")
    try:
        assert "".join([t async for t in relay.stream("hello")]) == "Hello there."
    finally:
        access_token.reset(binding)
    assert len(requests) == 1
    assert str(requests[0].url) == "https://api.example/api/v1/presence/complete"
    assert requests[0].headers["authorization"] == "Bearer session-token"
    assert json.loads(requests[0].content) == {"text": "hello", "provider": "gemini"}


@pytest.mark.parametrize("status", [301, 307, 401, 403, 409, 429, 500, 503])
async def test_refusal_never_calls_fallback_or_follows_redirect(status):
    requests = []
    def handle(request):
        requests.append(request)
        return httpx.Response(status, headers={"Location": "https://elsewhere.example"}, json={"detail": "SECRET"})
    relay = RelayTokenStreamer("gemini", "https://api.example", transport=httpx.MockTransport(handle))
    fallback = MockTokenStreamer("must not run", name="other-paid-provider")
    router = InferenceRouter(relay, fallback)
    binding = access_token.set("session-token")
    try:
        with pytest.raises(InferenceUnavailable) as caught:
            _ = [t async for t in router.stream("hello", TurnMetrics(turn_id="one"))]
    finally:
        access_token.reset(binding)
    assert "SECRET" not in str(caught.value)
    assert len(requests) == 1
    assert fallback.calls == 0
    assert router.breaker.total_breaches == 0


async def test_missing_auth_and_unconfirmed_success_are_terminal():
    requests = []
    def handle(request):
        requests.append(request)
        return httpx.Response(200, json={"provider": "gemini", "text": "do not speak"})
    relay = RelayTokenStreamer("gemini", "https://api.example", transport=httpx.MockTransport(handle))
    with pytest.raises(InferenceRefused, match="authentication"):
        _ = [t async for t in relay.stream("hello")]
    assert not requests
    binding = access_token.set("session-token")
    try:
        with pytest.raises(InferenceRefused, match="unconfirmed"):
            _ = [t async for t in relay.stream("hello")]
    finally:
        access_token.reset(binding)


async def test_shared_router_keeps_concurrent_session_tokens_separate():
    entered = 0
    both = asyncio.Event()
    seen = []
    async def handle(request):
        nonlocal entered
        entered += 1
        seen.append(request.headers["authorization"])
        if entered == 2:
            both.set()
        await both.wait()
        return httpx.Response(200, json={
            "provider": "gemini", "text": "ok", "usage_recorded": True,
            "usage": {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3},
        })
    relay = RelayTokenStreamer("gemini", "https://api.example", transport=httpx.MockTransport(handle))
    router = InferenceRouter(relay, ttft_threshold_ms=5000)
    async def send(message):
        pass
    sessions = [
        PresenceSession(session_id=str(i), user_id=str(i), inference_access_token=token,
                        router=router, speech=MockSpeech(), send=send, pacer=VirtualPacer())
        for i, token in enumerate(("owner-a-token", "owner-b-token"))
    ]
    await asyncio.gather(*[await s.begin_turn(str(i), "hello") for i, s in enumerate(sessions)])
    assert sorted(seen) == ["Bearer owner-a-token", "Bearer owner-b-token"]
    assert access_token.get() == ""


def test_websocket_hello_token_reaches_turn_task(monkeypatch):
    from fastapi.testclient import TestClient

    from apps.presence.main import create_app
    from test_presence_service import SETTINGS, hello, mint, run_turn
    seen = []
    class InspectToken(MockTokenStreamer):
        async def stream(self, prompt):
            seen.append(access_token.get())
            async for part in super().stream(prompt):
                yield part
    app = create_app(SETTINGS, primary=InspectToken("ok"), speech=MockSpeech(), pacer=VirtualPacer())
    token = mint()
    with TestClient(app).websocket_connect("/ws/presence") as ws:
        assert hello(ws, token)["t"] == "ready"
        ws.receive_json()
        run_turn(ws, "one", "hello")
    assert seen == [token]

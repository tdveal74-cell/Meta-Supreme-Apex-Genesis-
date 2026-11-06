"""Offline API relay acceptance: real auth/meter code, in-memory DB/provider seams.

No network or production database is touched by this file. Live acceptance is
a separate provider response and durable production ledger readback.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import httpx
import jwt
import pytest
from fastapi import FastAPI

from app.api.v1.presence import router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.tenant_context import TenantContextMiddleware, current_tenant_id
from app.db.session import get_db
from app.services import presence, provider_usage
from app.services.provider_usage import DailyUsage, MeteredProvider
from services.intelligence.presence import PRESENCE_SYSTEM_PROMPT
from services.intelligence.providers.base import AIProvider, CompletionResponse, TokenUsage
from services.intelligence.providers.gemini_provider import GeminiProvider


class FixtureProvider(AIProvider):
    name = "gemini"
    def __init__(self):
        super().__init__(default_model="fixture", max_retries=0)
        self.calls = []
        self.entered = asyncio.Event()
        self.release = None

    async def _complete_once(self, request):
        self.calls.append((current_tenant_id(), request))
        self.entered.set()
        if self.release is not None:
            await self.release.wait()
        return CompletionResponse(text="ok", provider=self.name, model="fixture", usage=TokenUsage(1413, 192))


@pytest.fixture
async def lane(monkeypatch):
    users = {str(uuid4()): SimpleNamespace(is_active=True) for _ in range(2)}
    for key, user in users.items():
        user.id = key
    class FakeSession:
        async def execute(self, stmt):
            identifier = stmt.compile().params["id_1"]
            return SimpleNamespace(scalar_one_or_none=lambda: users.get(identifier))
    async def db():
        yield FakeSession()

    ledger = {}
    writes = []
    async def read(owner, day=None):
        day = day or provider_usage.utc_today()
        values = ledger.get(owner, (0, 0, 0))
        return DailyUsage(owner, day, *values)
    async def record(owner, *, input_tokens, output_tokens, day=None):
        writes.append((owner, input_tokens, output_tokens))
        old = ledger.get(owner, (0, 0, 0))
        ledger[owner] = (old[0]+1, old[1]+input_tokens, old[2]+output_tokens)

    monkeypatch.setattr(provider_usage, "read_usage", read)
    monkeypatch.setattr(provider_usage, "record_usage", record)
    monkeypatch.setattr(settings, "PROVIDER_DAILY_TOKEN_CAP", 500000)
    provider = FixtureProvider()
    metered = MeteredProvider(provider, strict_recording=True)
    monkeypatch.setattr(presence, "get_presence_provider", lambda: metered)
    presence.start_accepting()
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.add_middleware(TenantContextMiddleware)
    register_exception_handlers(app)
    app.dependency_overrides[get_db] = db
    def token(owner, **claims):
        payload = {"sub": owner, "type": "access", "exp": datetime.now(timezone.utc)+timedelta(minutes=5)}
        payload.update(claims)
        return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://api.example") as client:
        yield SimpleNamespace(client=client, owners=list(users), users=users, token=token,
                              ledger=ledger, writes=writes, provider=provider, metered=metered)
    await presence.drain_completions()
    presence.start_accepting()


def headers(lane, owner):
    return {"Authorization": "Bearer " + lane.token(owner)}


async def call(lane, owner, **body):
    return await lane.client.post("/api/v1/presence/complete", headers=headers(lane, owner),
                                  json={"text": "hello", "provider": "gemini", **body})


async def test_authenticated_response_records_once_under_owner(lane):
    response = await call(lane, lane.owners[0])
    assert response.status_code == 200
    assert response.json()["usage"] == {"input_tokens": 1413, "output_tokens": 192, "total_tokens": 1605}
    assert response.json()["usage_recorded"] is True
    assert lane.writes == [(lane.owners[0], 1413, 192)]
    owner, request = lane.provider.calls[0]
    assert owner == lane.owners[0]
    assert request.system == PRESENCE_SYSTEM_PROMPT
    assert request.max_tokens == 200
    assert request.metadata == {"component": "devon-presence"}
    assert "system" not in lane.ledger


async def test_gemini_thinking_fixture_goes_through_real_parser_and_strict_meter(lane):
    requests = []
    def vendor(request):
        requests.append(request)
        return httpx.Response(200, json={"model": "gemini-fixture", "choices": [
            {"message": {"content": "ok"}, "finish_reason": "stop"}
        ], "usage": {"prompt_tokens": 1413, "completion_tokens": 40, "total_tokens": 1605}})
    lane.metered.inner = GeminiProvider(api_key="fixture", max_retries=0, transport=httpx.MockTransport(vendor))
    response = await call(lane, lane.owners[0])
    assert response.status_code == 200
    assert len(requests) == 1
    assert lane.ledger[lane.owners[0]] == (1, 1413, 192)


async def test_actual_auth_refuses_missing_expired_inactive_and_unknown_users(lane):
    payload = {"text": "hello", "provider": "gemini"}
    assert (await lane.client.post("/api/v1/presence/complete", json=payload)).status_code == 401
    expired = lane.token(lane.owners[0], exp=0)
    assert (await lane.client.post("/api/v1/presence/complete", json=payload,
            headers={"Authorization": "Bearer "+expired})).status_code == 401
    lane.users[lane.owners[0]].is_active = False
    assert (await call(lane, lane.owners[0])).status_code == 401
    assert (await call(lane, str(uuid4()))).status_code == 401
    assert not lane.provider.calls and not lane.writes


async def test_cap_refuses_before_provider_and_preserves_retry_after(lane):
    owner = lane.owners[0]
    lane.ledger[owner] = (10, 400000, 100000)
    response = await call(lane, owner)
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "provider_spend_cap"
    assert int(response.headers["Retry-After"]) > 0
    assert not lane.provider.calls and not lane.writes


async def test_mismatch_and_caller_overrides_cannot_start_inference(lane):
    assert (await call(lane, lane.owners[0], provider="openai")).status_code == 409
    assert (await call(lane, lane.owners[0], max_tokens=100000)).status_code == 422
    assert (await call(lane, lane.owners[0], system="override")).status_code == 422
    assert (await call(lane, lane.owners[0], text=" ")).status_code == 422
    assert not lane.provider.calls


async def test_failed_record_never_claims_acceptance_or_retries(lane, monkeypatch):
    async def broken(*args, **kwargs):
        raise RuntimeError("PRIVATE_DATABASE_CREDENTIAL")
    monkeypatch.setattr(provider_usage, "record_usage", broken)
    response = await call(lane, lane.owners[0])
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "provider_usage_unconfirmed"
    assert "PRIVATE" not in response.text
    assert len(lane.provider.calls) == 1


async def test_cancelled_http_wait_still_records_paid_result_for_original_owner(lane):
    lane.provider.release = asyncio.Event()
    owner = lane.owners[0]
    request = asyncio.create_task(call(lane, owner))
    await lane.provider.entered.wait()
    request.cancel()
    with pytest.raises(asyncio.CancelledError):
        await request
    assert len(presence._pending) == 1
    # A second tenant must not overwrite the owner copied into the first task.
    other = asyncio.create_task(call(lane, lane.owners[1]))
    await asyncio.sleep(0)
    lane.provider.release.set()
    assert (await other).status_code == 200
    await presence.drain_completions()
    assert sorted(lane.writes) == sorted([(owner, 1413, 192), (lane.owners[1], 1413, 192)])
    assert not presence._pending and "system" not in lane.ledger


async def test_capacity_refuses_new_work_but_drains_already_accepted_call(lane, monkeypatch):
    monkeypatch.setattr(presence, "MAX_PENDING_COMPLETIONS", 1)
    lane.provider.release = asyncio.Event()
    first = asyncio.create_task(call(lane, lane.owners[0]))
    await lane.provider.entered.wait()
    response = await call(lane, lane.owners[1])
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "presence_capacity"
    assert len(lane.provider.calls) == 1
    lane.provider.release.set()
    assert (await first).status_code == 200


def test_factory_is_strict_metered_zero_retry_and_uses_api_model(monkeypatch):
    # Recreate the factory wrapper because lane replaces it per test.
    original = presence.get_presence_provider
    original.cache_clear()
    monkeypatch.setattr(settings, "DEFAULT_AI_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "fixture-key")
    monkeypatch.setattr(settings, "GEMINI_MODEL", "gemini-fixture")
    monkeypatch.setattr(settings, "AI_MODEL", "")
    try:
        provider = original()
        assert isinstance(provider, MeteredProvider) and provider.strict_recording
        assert isinstance(provider.inner, GeminiProvider)
        assert provider.max_retries == provider.inner.max_retries == 0
        assert provider.default_model == "gemini-fixture"
    finally:
        original.cache_clear()

async def test_ttft_fallback_cancels_relay_wait_but_not_api_meter(lane):
    from apps.presence.breaker import InferenceRouter, TurnMetrics
    from apps.presence.inference import MockTokenStreamer
    from apps.presence.relay import RelayTokenStreamer, access_token

    lane.provider.release = asyncio.Event()
    relay = RelayTokenStreamer(
        "gemini", "https://api.example", transport=lane.client._transport
    )
    fallback = MockTokenStreamer("offline")
    router = InferenceRouter(relay, fallback, ttft_threshold_ms=20)
    binding = access_token.set(lane.token(lane.owners[0]))
    try:
        result = [part async for part in router.stream("hello", TurnMetrics(turn_id="slow"))]
    finally:
        access_token.reset(binding)
    assert "".join(result) == "offline" and fallback.calls == 1
    assert len(lane.provider.calls) == 1 and not lane.writes
    assert len(presence._pending) == 1
    lane.provider.release.set()
    await presence.drain_completions()
    assert lane.writes == [(lane.owners[0], 1413, 192)]


async def test_shutdown_drains_paid_work_and_refuses_new_calls(lane):
    lane.provider.release = asyncio.Event()
    first = asyncio.create_task(call(lane, lane.owners[0]))
    await lane.provider.entered.wait()
    drain = asyncio.create_task(presence.drain_completions())
    await asyncio.sleep(0)
    assert (await call(lane, lane.owners[1])).status_code == 429
    lane.provider.release.set()
    assert (await first).status_code == 200
    await drain
    assert not presence._pending
    assert lane.writes == [(lane.owners[0], 1413, 192)]

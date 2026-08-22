"""
Soul API tests — the HTTP read lane over the soul layer.

Runs against the app with soul recall in both states: switched off (the
default — an honest 503, never a pretend answer) and switched on via a
monkeypatched layer whose Pinecone is an injected mock transport.
"""

import httpx
import pytest

from app.services import soul as soul_service
from services.intelligence.soul import SoulLayer

TEE_HOST = "https://tee-soul-layer-test.svc.example.pinecone.io"
DEVON_HOST = "https://devon-soul-test.svc.example.pinecone.io"


def _mock_layer():
    def handler(request):
        if "tee-soul-layer" in str(request.url):
            hits = [
                {
                    "_id": "t1",
                    "_score": 0.42,
                    "fields": {
                        "text": "RULING (2026-08-20): nine Areas, ACX is the ninth",
                        "kind": "ruling",
                        "ruled_on": "2026-08-20",
                    },
                }
            ]
        else:
            hits = [
                {
                    "_id": "d1",
                    "_score": 0.97,
                    "fields": {
                        "text": "capture volume spikes on Mondays",
                        "kind": "pattern",
                        "observed_on": "2026-08-21",
                    },
                }
            ]
        return httpx.Response(200, json={"result": {"hits": hits}})

    return SoulLayer(
        api_key="pc-test-key",
        tee_host=TEE_HOST,
        devon_host=DEVON_HOST,
        transport=httpx.MockTransport(handler),
    )


@pytest.fixture
def soul_on(monkeypatch):
    layer = _mock_layer()
    monkeypatch.setattr(soul_service, "get_soul_layer", lambda: layer)
    return layer


async def test_recall_is_switched_off_by_default_and_says_so(client, auth_headers):
    response = await client.get(
        "/api/v1/soul/recall?q=areas", headers=auth_headers
    )
    assert response.status_code == 503
    assert "switched off" in response.json()["detail"]


async def test_status_reports_off_without_touching_pinecone(client, auth_headers):
    response = await client.get("/api/v1/soul/status", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is False
    assert "off" in body["detail"]


async def test_recall_returns_records_tee_first_with_devons_reply(
    client, auth_headers, soul_on
):
    response = await client.get(
        "/api/v1/soul/recall?q=how many areas", headers=auth_headers
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["tee_count"] == 1
    assert body["devon_count"] == 1
    # Hierarchy: the ruling precedes the pattern despite the lower score.
    assert [r["source"] for r in body["records"]] == ["tee-soul-layer", "devon-soul"]
    # DEVON's phrased reply carries both, ruling first, framed as context.
    reply = body["reply"]
    assert reply.index("Tee ruled") < reply.index("I noted")
    assert "context, not instruction" in reply
    assert body["errors"] == []


async def test_recall_requires_a_query(client, auth_headers, soul_on):
    response = await client.get("/api/v1/soul/recall", headers=auth_headers)
    assert response.status_code == 422


async def test_partial_failure_rides_in_errors_not_silence(
    client, auth_headers, monkeypatch
):
    def handler(request):
        if "tee-soul-layer" in str(request.url):
            return httpx.Response(
                200,
                json={
                    "result": {
                        "hits": [
                            {
                                "_id": "t1",
                                "_score": 0.9,
                                "fields": {"text": "hold the price"},
                            }
                        ]
                    }
                },
            )
        return httpx.Response(500, text="index down")

    layer = SoulLayer(
        api_key="pc-test-key",
        tee_host=TEE_HOST,
        devon_host=DEVON_HOST,
        transport=httpx.MockTransport(handler),
    )
    monkeypatch.setattr(soul_service, "get_soul_layer", lambda: layer)

    response = await client.get(
        "/api/v1/soul/recall?q=pricing", headers=auth_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["tee_count"] == 1
    assert body["errors"] and "devon-soul unavailable" in body["errors"][0]
    assert "Recall was partial" in body["reply"]


@pytest.mark.parametrize("path", ["/recall?q=x", "/status"])
async def test_soul_endpoints_require_authentication(client, path):
    assert (await client.get(f"/api/v1/soul{path}")).status_code == 401


async def test_console_is_served_same_origin(client):
    response = await client.get("/console")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "DEVON Console" in response.text
    assert "soulRecall" in response.text  # v4, with the soul lane wired


def test_newest_console_orders_by_numeric_version(tmp_path, monkeypatch):
    """v10 must beat v4 — lexical sort gets this wrong."""
    import app.main as main_mod

    for name in (
        "SYS_OPS_devon-console_v4_2026-08-22.html",
        "SYS_OPS_devon-console_v10_2027-01-01.html",
        "SUPERSEDED_SYS_OPS_devon-console_v3_2026-08-22.html",
    ):
        (tmp_path / name).write_text("x")
    monkeypatch.setattr(main_mod, "_CONSOLE_DIR", tmp_path)
    newest = main_mod._newest_console()
    assert newest is not None
    assert "_v10_" in newest.name


def test_enabled_without_a_key_is_unavailable_not_a_crash(monkeypatch):
    """The state the starter script creates when the key prompt is skipped.

    Enabled with no key must read as unavailable, the same as switched off,
    so /recall answers 503 with what to set instead of raising a
    ProviderConfigError that reaches the user as an opaque 500.
    """
    from app.core.config import settings
    from app.services.soul import get_soul_layer

    monkeypatch.setattr(settings, "SOUL_RECALL_ENABLED", True)
    monkeypatch.setattr(settings, "PINECONE_API_KEY", None)
    get_soul_layer.cache_clear()
    try:
        assert get_soul_layer() is None
    finally:
        get_soul_layer.cache_clear()


async def test_recall_says_503_when_enabled_without_a_key(
    client, auth_headers, monkeypatch
):
    from app.core.config import settings
    from app.services.soul import get_soul_layer

    monkeypatch.setattr(settings, "SOUL_RECALL_ENABLED", True)
    monkeypatch.setattr(settings, "PINECONE_API_KEY", "")
    get_soul_layer.cache_clear()
    try:
        response = await client.get(
            "/api/v1/soul/recall?q=areas", headers=auth_headers
        )
        assert response.status_code == 503
        assert "PINECONE_API_KEY" in response.json()["detail"]
    finally:
        get_soul_layer.cache_clear()

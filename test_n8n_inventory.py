"""Executed offline checks of owner isolation, nonmutation and honest discovery."""

import asyncio
import json
from types import SimpleNamespace
from urllib.parse import parse_qs

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.api.v1 import n8n_inventory as route
from app.core.tenant_context import bind_tenant, reset_tenant
from app.security.deps import get_current_user
from app.services import conversation_tools
from app.services import n8n_inventory as inv
from services.agent_runtime.contracts import ToolRisk
from services.agent_runtime.tools import ToolRegistry

OWNER = "11111111-1111-4111-8111-111111111111"
OTHER = "22222222-2222-4222-8222-222222222222"
VERSION = "33333333-3333-4333-8333-333333333333"
KEY = "test-inventory-key-never-real"


def config(**changes):
    return {inv.OWNER_VARIABLE: OWNER, "N8N_API_URL": inv.N8N_HOST, "N8N_API_KEY": KEY, **changes}


def row(identifier="new_workflow", **changes):
    return {
        "id": identifier, "name": "New self-hosted workflow", "active": True,
        "isArchived": False, "activeVersionId": VERSION,
        "updatedAt": "2026-10-22T08:00:00Z", **changes,
    }


def fetch_pages(pages, calls):
    async def fetch(url, key):
        calls.append((url, key))
        page = pages[len(calls) - 1]
        if isinstance(page, Exception):
            raise page
        return page
    return fetch


@pytest.mark.asyncio
@pytest.mark.parametrize("caller,environment,state", [
    (OWNER, {}, "disabled"),
    (OWNER, {inv.OWNER_VARIABLE: "not-a-uuid"}, "disabled"),
    (OTHER, config(), "forbidden"),
    (None, config(), "forbidden"),
    ("system", config(), "forbidden"),
])
async def test_default_disabled_and_other_owners_never_reach_network(caller, environment, state):
    calls = []
    with pytest.raises(inv.InventoryAccessError) as exc:
        await inv.read_inventory(caller, environ=environment, fetcher=fetch_pages([], calls))
    assert exc.value.state == state
    assert calls == []


@pytest.mark.asyncio
async def test_live_pages_project_only_metadata_and_do_not_infer_editor_version():
    calls = []
    secret = "NODE-PARAMETER-OR-CREDENTIAL-MUST-NOT-ESCAPE"
    first = row(nodes=[{"parameters": {"token": secret}}], credentials={"key": secret},
                settings={"secret": secret}, pinData={"secret": secret})
    second = row("second", active=False, activeVersionId=None, versionId=VERSION, isArchived=None)
    payload = await inv.read_inventory(OWNER, environ=config(), fetcher=fetch_pages([
        {"data": [first], "nextCursor": "next?token=evil&host=elsewhere"},
        {"data": [second], "nextCursor": None},
    ], calls))
    assert payload["state"] == "ok" and payload["complete"]
    assert payload["pages_read"] == 2
    assert payload["counts"] == {"observed": 2, "active_observed": 1, "archive_state_unknown": 1}
    assert secret not in json.dumps(payload)
    assert set(payload["workflows"][0]) == {
        "id", "name", "active", "is_archived", "published_version_id", "updated_at",
    }
    assert payload["workflows"][1]["published_version_id"] is None
    for url, key in calls:
        assert url.startswith(inv.N8N_HOST + "/api/v1/workflows?")
        assert key == KEY
    assert parse_qs(calls[1][0].split("?", 1)[1])["cursor"] == ["next?token=evil&host=elsewhere"]


@pytest.mark.asyncio
async def test_secondary_canonical_host_uses_its_own_key_and_never_reads_cloud():
    calls = []
    env = config(N8N_API_URL="https://old.app.n8n.cloud", N8N_API_KEY="cloud-key",
                 N8N_SECONDARY_API_URL=inv.N8N_HOST, N8N_SECONDARY_API_KEY=KEY)
    payload = await inv.read_inventory(OWNER, environ=env, fetcher=fetch_pages([{"data": [], "nextCursor": None}], calls))
    assert payload["complete"] and len(calls) == 1
    assert calls[0][1] == KEY and "cloud" not in calls[0][0]


@pytest.mark.asyncio
@pytest.mark.parametrize("url", [
    "https://old.app.n8n.cloud", "http://n8n.editforge.online", "https://n8n.editforge.online.evil",
    "https://key@n8n.editforge.online", "https://n8n.editforge.online/?redirect=elsewhere",
])
async def test_alternate_origins_and_cloud_have_no_fallback(url):
    calls = []
    payload = await inv.read_inventory(OWNER, environ=config(N8N_API_URL=url), fetcher=fetch_pages([], calls))
    assert payload["state"] == "failed" and not payload["complete"] and calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("changes", [
    {"N8N_SECONDARY_API_URL": inv.N8N_HOST, "N8N_SECONDARY_API_KEY": KEY},
    {"N8N_API_KEY": ""},
])
async def test_ambiguous_or_missing_paired_key_refuses_without_network(changes):
    calls = []
    payload = await inv.read_inventory(OWNER, environ=config(**changes), fetcher=fetch_pages([], calls))
    assert payload["state"] == "failed" and not payload["complete"] and calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_page", [
    None, {}, {"data": {}}, {"data": []},
    {"data": [row(active="true")], "nextCursor": None},
    {"data": [row(id="../execute")], "nextCursor": None},
    {"data": [row(isArchived=1)], "nextCursor": None},
    {"data": [row(activeVersionId="editor-version-not-published")], "nextCursor": None},
    {"data": [row(updatedAt="yesterday")], "nextCursor": None},
    {"data": [row(name="")], "nextCursor": None},
    {"data": [row()], "nextCursor": 12}, {"data": [row()] * 101, "nextCursor": None},
])
async def test_malformed_page_is_failed_never_empty_success(bad_page):
    calls = []
    payload = await inv.read_inventory(OWNER, environ=config(), fetcher=fetch_pages([bad_page], calls))
    assert payload["state"] == "failed" and not payload["complete"]
    assert payload["workflows"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize("second", [
    {"data": [row()], "nextCursor": None},
    {"data": [row("second")], "nextCursor": "repeat"},
    inv.InventoryReadError("inventory HTTP read refused"),
])
async def test_bad_later_page_preserves_first_page_as_partial(second):
    calls = []
    payload = await inv.read_inventory(OWNER, environ=config(), fetcher=fetch_pages([
        {"data": [row()], "nextCursor": "repeat"}, second,
    ], calls))
    assert payload["state"] == "partial" and not payload["complete"]
    assert payload["pages_read"] == 1 and payload["counts"]["observed"] == 1


@pytest.mark.asyncio
async def test_total_time_and_page_bounds_are_explicit(monkeypatch):
    monkeypatch.setattr(inv, "MAX_PAGES", 1)
    calls = []
    payload = await inv.read_inventory(OWNER, environ=config(), fetcher=fetch_pages([
        {"data": [row()], "nextCursor": "more"},
    ], calls))
    assert payload["state"] == "partial" and "page bound" in payload["error"]
    monkeypatch.setattr(inv, "TOTAL_TIMEOUT_SECONDS", 0.01)

    async def stalled(url, key):
        await asyncio.Event().wait()
    payload = await inv.read_inventory(OWNER, environ=config(), fetcher=stalled)
    assert payload["state"] == "failed" and "time bound" in payload["error"]


def transport(monkeypatch, handler):
    original = httpx.AsyncClient
    options = []

    def client(**kwargs):
        options.append(kwargs)
        return original(**kwargs, transport=httpx.MockTransport(handler))
    monkeypatch.setattr(httpx, "AsyncClient", client)
    return options


@pytest.mark.asyncio
async def test_actual_transport_sends_get_only_and_refuses_redirect_without_forwarding_key(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(302, headers={"Location": "https://other.invalid/leak"})
    options = transport(monkeypatch, handler)
    with pytest.raises(inv.InventoryReadError, match="HTTP read refused"):
        await inv._fetch_page(inv._url(None), KEY)
    assert len(calls) == 1
    assert calls[0].method == "GET"
    assert calls[0].url.host == "n8n.editforge.online"
    assert calls[0].headers["X-N8N-API-KEY"] == KEY
    assert options[0]["follow_redirects"] is False and options[0]["trust_env"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["oversize", "bad_json", "http_error", "network_error"])
async def test_actual_transport_bounds_and_errors_do_not_return_bodies_or_keys(monkeypatch, kind):
    def handler(request):
        if kind == "network_error":
            raise httpx.ConnectError("private-secret-provider-text", request=request)
        if kind == "http_error":
            return httpx.Response(401, text="private-secret-provider-text")
        return httpx.Response(200, content=b"x" * 33 if kind == "oversize" else b"not json")
    transport(monkeypatch, handler)
    monkeypatch.setattr(inv, "MAX_PAGE_BYTES", 32)
    with pytest.raises(inv.InventoryReadError) as exc:
        await inv._fetch_page(inv._url(None), KEY)
    assert "private-secret" not in str(exc.value) and KEY not in str(exc.value)


def test_route_requires_auth_and_separate_owner_binding(monkeypatch):
    app = FastAPI()
    app.include_router(route.router)
    client = TestClient(app)

    async def unauthenticated():
        raise HTTPException(401, "Not authenticated")
    app.dependency_overrides[get_current_user] = unauthenticated
    assert client.get("/n8n/workflows").status_code == 401
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=OTHER)
    monkeypatch.setenv(inv.OWNER_VARIABLE, OWNER)
    assert client.get("/n8n/workflows").status_code == 403
    monkeypatch.delenv(inv.OWNER_VARIABLE)
    assert client.get("/n8n/workflows").status_code == 503
    for verb in ("POST", "PUT", "PATCH", "DELETE"):
        assert client.request(verb, "/n8n/workflows").status_code == 405


def test_authenticated_owner_route_runs_real_service_with_metadata_only_transport(monkeypatch):
    for key, value in config().items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("N8N_SECONDARY_API_URL", raising=False)
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"data": [row(nodes=[{"credentials": "hidden"}])], "nextCursor": None})
    transport(monkeypatch, handler)
    app = FastAPI()
    app.include_router(route.router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=OWNER)
    response = TestClient(app).get("/n8n/workflows")
    assert response.status_code == 200 and response.json()["complete"]
    assert response.json()["workflows"][0]["id"] == "new_workflow"
    assert "hidden" not in response.text and "nodes" not in response.text
    assert len(calls) == 1 and calls[0].method == "GET"


@pytest.mark.asyncio
async def test_conversation_uses_authenticated_binding_not_model_owner_and_fits_budget(monkeypatch):
    seen = []

    async def read(owner):
        seen.append(owner)
        inv.authorize(owner, config())
        return {
            "state": "ok", "complete": True, "source": inv.N8N_HOST,
            "observed_at": "2026-10-22T08:00:00Z", "error": None,
            "workflows": [inv._project(row(str(i), name="\x00" * 256)) for i in range(10)],
        }
    monkeypatch.setattr(conversation_tools, "read_inventory", read)
    tools = conversation_tools.build_conversation_tool_registry(base_registry=ToolRegistry())
    spec = tools.require("n8n.workflow_inventory")
    assert spec.risk is ToolRisk.READ and not spec.approval_required
    token = bind_tenant(OTHER)
    try:
        refused = await tools.execute(spec.name, {"query": ""})
        assert not refused.ok and refused.output == ""
        spoof = await tools.execute(spec.name, {"owner_id": OWNER})
        assert not spoof.ok and seen == [OTHER]
    finally:
        reset_tenant(token)
    token = bind_tenant(OWNER)
    try:
        result = await tools.execute(spec.name, {"query": "", "offset": 0})
        assert result.ok and len(result.output) <= 1000
        view = json.loads(result.output)
        assert view["workflows"][0]["id"] == "0" and view["next_offset"] == 1
        assert view["workflows"][0]["name_truncated"]
        result = await tools.execute(spec.name, {"offset": view["next_offset"]})
        assert json.loads(result.output)["workflows"][0]["id"] == "1"
    finally:
        reset_tenant(token)


@pytest.mark.asyncio
async def test_conversation_failure_does_not_report_empty_success(monkeypatch):
    async def read(owner):
        return {
            "state": "failed", "complete": False, "source": inv.N8N_HOST,
            "observed_at": "2026-10-22T08:00:00Z", "error": "inventory HTTP read refused", "workflows": [],
        }
    monkeypatch.setattr(conversation_tools, "read_inventory", read)
    tools = conversation_tools.build_conversation_tool_registry(base_registry=ToolRegistry())
    result = await tools.execute("n8n.workflow_inventory", {})
    assert not result.ok and len(result.error) <= 500
    assert json.loads(result.error)["state"] == "failed"

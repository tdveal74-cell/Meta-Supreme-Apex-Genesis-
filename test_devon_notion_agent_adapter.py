"""Network-isolated tests for the DEVON Notion capability adapter."""

import json

import httpx
import pytest

INBOX_DB = "4deffb01-5662-4422-bdcd-b3e6f6a64d22"
PAGE_ID = "1" * 32


def _page(parent=INBOX_DB):
    return {
        "object": "page",
        "id": PAGE_ID,
        "url": "https://www.notion.so/" + PAGE_ID,
        "created_time": "2026-10-24T12:00:00.000Z",
        "parent": {"type": "database_id", "database_id": parent},
        "properties": {
            "Name": {"type": "title", "title": [{"plain_text": "Weekly review idea"}]},
            "Type": {"type": "select", "select": {"name": "Idea"}},
            "Tags": {"type": "multi_select", "multi_select": [{"name": "Systems"}]},
        },
    }


def _configure_notion(monkeypatch, handler):
    from app.services.agent_tasks import notion_client

    monkeypatch.setattr(notion_client, "token", "test-notion-secret")
    monkeypatch.setattr(notion_client, "base_url", "https://api.notion.test")
    monkeypatch.setattr(notion_client, "transport", httpx.MockTransport(handler))
    return notion_client


@pytest.mark.asyncio
async def test_notion_create_page_waits_for_approval_then_writes_and_reads_back(
    client, auth_headers, monkeypatch
):
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["authorization"] == "Bearer test-notion-secret"
        assert request.headers["notion-version"] == "2022-06-28"
        if request.method == "POST":
            body = json.loads(request.content)
            assert body["parent"] == {"database_id": INBOX_DB}
            assert body["properties"]["Name"]["title"][0]["text"]["content"] == "Weekly review idea"
            assert body["properties"]["Type"] == {"select": {"name": "Idea"}}
            assert body["properties"]["Tags"] == {"multi_select": [{"name": "Systems"}]}
            assert body["children"][0]["paragraph"]["rich_text"][0]["text"]["content"] == "Every Sunday."
            return httpx.Response(200, json={"id": PAGE_ID, "url": "https://www.notion.so/x"})
        assert request.url.path == f"/v1/pages/{PAGE_ID}"
        return httpx.Response(200, json=_page())

    _configure_notion(monkeypatch, handler)

    catalog = await client.get("/api/v1/agent-tasks/tools", headers=auth_headers)
    specs = {item["name"]: item for item in catalog.json()["tools"]}
    assert specs["notion.create_page"]["approval_required"] is True
    assert specs["notion.read_page"]["approval_required"] is False

    created = await client.post(
        "/api/v1/agent-tasks",
        headers=auth_headers,
        json={
            "goal": "Capture an idea",
            "steps": [
                {
                    "title": "File to the Inbox",
                    "tool": "notion.create_page",
                    "arguments": {
                        "database": "inbox",
                        "title": "Weekly review idea",
                        "properties": {"Type": "Idea", "Tags": ["Systems"]},
                        "body": "Every Sunday.",
                    },
                }
            ],
        },
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["task_id"]
    waiting = await client.post(f"/api/v1/agent-tasks/{task_id}/run", headers=auth_headers, json={})
    assert waiting.json()["task"]["state"] == "waiting_approval"
    assert requests == []

    step = waiting.json()["task"]["plan"]["steps"][0]
    decision = await client.post(
        "/api/v1/devon/approvals/decide",
        headers=auth_headers,
        json={
            "request_id": step["approval_request_id"],
            "token": waiting.json()["approval_token"],
            "decision": "approve",
            "decided_by": "Tee",
        },
    )
    assert decision.json()["approved"] is True

    resumed = await client.post(f"/api/v1/agent-tasks/{task_id}/run", headers=auth_headers, json={})
    task = resumed.json()["task"]
    assert task["state"] == "completed", resumed.text
    assert [r.method for r in requests] == ["POST", "GET"]
    assert PAGE_ID in task["observations"][0]["output"]
    assert "test-notion-secret" not in resumed.text


@pytest.mark.asyncio
async def test_a_page_that_reads_back_under_another_parent_is_not_reported_done():
    from services.notion.client import NotionRESTClient, NotionRESTError

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(200, json={"id": PAGE_ID})
        return httpx.Response(200, json=_page(parent="9" * 32))

    notion = NotionRESTClient(token="t", base_url="https://api.notion.test", transport=httpx.MockTransport(handler))
    with pytest.raises(NotionRESTError, match="reads back under parent"):
        await notion.create_page("inbox", title="An idea worth keeping")


@pytest.mark.asyncio
async def test_a_create_with_no_page_id_is_not_reported_done():
    from services.notion.client import NotionRESTClient, NotionRESTError

    notion = NotionRESTClient(
        token="t",
        base_url="https://api.notion.test",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})),
    )
    with pytest.raises(NotionRESTError, match="without a page id"):
        await notion.create_page("tasks", title="Call the bank")


@pytest.mark.parametrize(
    "database,properties,match",
    [
        ("calendar", {}, "not allowlisted"),
        ("inbox", {"Type": "Memo"}, "Type must be one of"),
        ("inbox", {"Tags": ["Systems", "Gardening"]}, "Gardening"),
        ("inbox", {"Owner": "Tee"}, "not writable"),
        ("tasks", {"Due": "next friday"}, "YYYY-MM-DD"),
        ("tasks", {"Due": "2026-02-30"}, "not a real date"),
        ("projects", {"Status": "Shipped"}, "Status must be one of"),
    ],
)
def test_build_page_refuses_what_the_schema_does_not_carry(database, properties, match):
    from services.notion.client import NotionRESTClient, NotionRESTError

    with pytest.raises(NotionRESTError, match=match):
        NotionRESTClient(token="t").build_page(database, title="A real title", properties=properties)


def test_build_page_maps_every_property_kind():
    from services.notion.client import NotionRESTClient

    page = NotionRESTClient(token="t").build_page(
        "tasks",
        title="  Renew   the domain ",
        properties={"Area": "Systems", "Due": "2026-11-01", "Notes": "Before it lapses", "Priority": "High", "Status": "Next"},
        body="One.\n\nTwo.",
    )
    props = page["properties"]
    assert props["Name"]["title"][0]["text"]["content"] == "Renew the domain"
    assert props["Due"] == {"date": {"start": "2026-11-01"}}
    assert props["Notes"]["rich_text"][0]["text"]["content"] == "Before it lapses"
    assert props["Priority"] == {"select": {"name": "High"}}
    assert [b["paragraph"]["rich_text"][0]["text"]["content"] for b in page["children"]] == ["One.", "Two."]


@pytest.mark.asyncio
async def test_a_bad_option_is_refused_before_the_approval_is_spent():
    """A typo must cost a correction, not a ruling."""
    from services.agent_runtime.governance import (
        APPROVAL_METADATA_KEY,
        RUNTIME_REQUESTED_BY,
        approval_binding,
        approval_marker,
    )
    from services.agent_runtime.tools import ToolRegistry
    from services.devon.approval import ApprovalQueue, ApprovalState
    from services.notion.agent_adapter import NotionCapabilityAdapter
    from services.notion.client import NotionRESTClient

    calls = []
    approvals = ApprovalQueue()
    args = {"database": "inbox", "title": "An idea", "properties": {"Type": "Memo"}}
    binding = approval_binding(task_id="T", step_id="S", tool_name="notion.create_page", arguments=args)
    record, token = approvals.request(
        title="Bound Notion page",
        what_happens=f"Create one page. {approval_marker(binding)}",
        requested_by=RUNTIME_REQUESTED_BY,
    )
    assert approvals.decide(record.request_id, token, "approve").approved

    registry = ToolRegistry()
    NotionCapabilityAdapter(
        NotionRESTClient(token="t", transport=httpx.MockTransport(lambda r: calls.append(r) or httpx.Response(500))),
        approvals,
    ).register(registry)
    result = await registry.execute(
        "notion.create_page",
        {**args, APPROVAL_METADATA_KEY: {"request_id": record.request_id, "binding": binding, "task_id": "T", "step_id": "S", "tool_name": "notion.create_page"}},
    )
    assert result.ok is False
    assert "approval was not spent" in result.error
    assert calls == []
    assert approvals.get(record.request_id).state is ApprovalState.APPROVED


@pytest.mark.asyncio
async def test_read_page_refuses_a_page_outside_the_allowlisted_databases():
    from services.notion.client import NotionRESTClient, NotionRESTError

    notion = NotionRESTClient(
        token="t",
        base_url="https://api.notion.test",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=_page(parent="9" * 32))),
    )
    with pytest.raises(NotionRESTError, match="not in an allowlisted"):
        await notion.read_page(PAGE_ID)


def test_notion_client_reads_only_the_devon_token(monkeypatch):
    from services.notion.client import NotionRESTClient

    monkeypatch.delenv("DEVON_NOTION_TOKEN", raising=False)
    monkeypatch.setenv("NOTION_TOKEN", "generic-token-that-must-not-be-used")
    assert NotionRESTClient().configured is False


def test_every_database_in_the_map_carries_the_nine_areas_where_it_has_an_area():
    from services.devon import areas as areas_mod
    from services.devon.vault import NOTION_DATABASES

    nine = {a.label for a in areas_mod.AREAS}
    for name, spec in NOTION_DATABASES.items():
        area = spec["properties"].get("Area")
        if area:
            assert set(area[1]) == nine, name

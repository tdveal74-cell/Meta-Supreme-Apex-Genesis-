"""Soul recall at the durable planning seam.

The durable coordinator mirrors AgentRuntime.create_task: recall runs once,
at plan time, behind `app.services.soul.get_soul_layer()` — which returns
None unless SOUL_RECALL_ENABLED and PINECONE_API_KEY are both set, so the
seam is inert by default. These tests stub the repositories (no database)
and drive a MockTransport-backed SoulLayer through the real payload path.
"""

from __future__ import annotations

import httpx
import pytest

import app.services.agent_tasks as agent_tasks_module
from services.intelligence.soul import CONTEXT_NOT_COMMAND, SoulLayer

TEE_HOST = "https://tee-soul-layer-test.svc.example.pinecone.io"
DEVON_HOST = "https://devon-soul-test.svc.example.pinecone.io"

PLANNED_STEPS = [
    {
        "title": "Inspect",
        "tool": "operator.read",
        "arguments": {"command": "pwd"},
    }
]


def _stub_persistence(monkeypatch, service) -> None:
    async def fake_context_for(db, *, owner_id, goal, project_id=None):
        return {"memories": [], "skills": []}

    async def fake_save(db, *, owner_id, task, project_id=None):
        return None

    monkeypatch.setattr(service.learning, "context_for", fake_context_for)
    monkeypatch.setattr(service.tasks, "save", fake_save)


@pytest.mark.asyncio
async def test_durable_create_task_recalls_when_the_soul_layer_is_live(
    monkeypatch,
) -> None:
    def handler(request):
        if "tee-soul-layer" in str(request.url):
            hits = [
                {
                    "_id": "t1",
                    "_score": 0.2,
                    "fields": {"text": "the ruling", "ruled_on": "2026-08-20"},
                }
            ]
        else:
            hits = [
                {
                    "_id": "d1",
                    "_score": 0.9,
                    "fields": {"text": "the pattern", "observed_on": "2026-08-21"},
                }
            ]
        return httpx.Response(200, json={"result": {"hits": hits}})

    soul = SoulLayer(
        api_key="pc-test-key",
        tee_host=TEE_HOST,
        devon_host=DEVON_HOST,
        transport=httpx.MockTransport(handler),
    )
    monkeypatch.setattr(agent_tasks_module, "get_soul_layer", lambda: soul)

    service = agent_tasks_module.DurableAgentTaskService()
    _stub_persistence(monkeypatch, service)

    task = await service.create_task(
        None,
        owner_id="owner-1",
        goal="Ship the release",
        planned_steps=PLANNED_STEPS,
    )

    payload = task.context["soul_recall"]
    assert payload["context"].startswith(CONTEXT_NOT_COMMAND)
    assert [r["source"] for r in payload["records"]] == [
        "tee-soul-layer",
        "devon-soul",
    ]
    assert payload["errors"] == []
    # The existing learning context is untouched beside it.
    assert "devon_learning" in task.context


@pytest.mark.asyncio
async def test_durable_create_task_swallows_a_soul_outage(monkeypatch) -> None:
    def handler(request):
        return httpx.Response(500, text="index melting")

    soul = SoulLayer(
        api_key="pc-test-key",
        tee_host=TEE_HOST,
        devon_host=DEVON_HOST,
        transport=httpx.MockTransport(handler),
    )
    monkeypatch.setattr(agent_tasks_module, "get_soul_layer", lambda: soul)

    service = agent_tasks_module.DurableAgentTaskService()
    _stub_persistence(monkeypatch, service)

    task = await service.create_task(
        None,
        owner_id="owner-1",
        goal="Anything",
        planned_steps=PLANNED_STEPS,
    )

    payload = task.context["soul_recall"]
    assert payload["records"] == []
    assert len(payload["errors"]) == 2  # both souls named their failure
    assert any("tee-soul-layer" in e for e in payload["errors"])
    assert any("devon-soul" in e for e in payload["errors"])


@pytest.mark.asyncio
async def test_durable_create_task_is_inert_without_a_soul_layer(
    monkeypatch,
) -> None:
    monkeypatch.setattr(agent_tasks_module, "get_soul_layer", lambda: None)

    service = agent_tasks_module.DurableAgentTaskService()
    _stub_persistence(monkeypatch, service)

    task = await service.create_task(
        None,
        owner_id="owner-1",
        goal="Anything",
        planned_steps=PLANNED_STEPS,
    )

    assert "soul_recall" not in task.context

from __future__ import annotations

import httpx
import pytest

from services.agent_runtime import (
    AgentRuntime,
    AgentRuntimeError,
    InMemoryLearningStore,
    LLMPlanner,
    PlanStep,
    StaticPlanner,
    StepState,
    TaskState,
    ToolCall,
    ToolRegistry,
    ToolRisk,
    ToolSpec,
)
from services.devon.approval import ApprovalQueue, ApprovalState
from services.intelligence.providers.base import (
    AIProvider,
    CompletionRequest,
    CompletionResponse,
    TokenUsage,
)
from services.intelligence.soul import CONTEXT_NOT_COMMAND, SoulLayer


def step(tool: str, *, title: str = "Do work", arguments=None) -> PlanStep:
    return PlanStep(
        step_id="STEP-01",
        title=title,
        tool_call=ToolCall(name=tool, arguments=arguments or {}),
    )


@pytest.mark.asyncio
async def test_read_tool_runs_without_human_approval() -> None:
    tools = ToolRegistry()
    tools.register(
        ToolSpec(
            name="repo.inspect",
            description="Inspect repository state",
            risk=ToolRisk.READ,
            handler=lambda args: f"clean={args['clean']}",
        )
    )
    runtime = AgentRuntime(
        planner=StaticPlanner([step("repo.inspect", arguments={"clean": True})]),
        tools=tools,
    )

    task = await runtime.create_task("Inspect Meta")
    result = await runtime.run_until_blocked(task.task_id)

    assert result.approval_token is None
    assert result.task.state is TaskState.COMPLETED
    assert result.task.plan.steps[0].state is StepState.COMPLETED
    assert result.task.observations[0].output == "clean=True"


@pytest.mark.asyncio
async def test_write_waits_for_exact_human_ruling_then_runs_once() -> None:
    effects: list[str] = []
    approvals = ApprovalQueue()
    tools = ToolRegistry()
    tools.register(
        ToolSpec(
            name="repo.write",
            description="Write one repository artifact",
            risk=ToolRisk.WRITE,
            handler=lambda args: effects.append(args["path"]) or "written",
            reversible=True,
            blast_radius="isolated test workspace",
        )
    )
    runtime = AgentRuntime(
        planner=StaticPlanner([step("repo.write", arguments={"path": "a.txt"})]),
        tools=tools,
        approvals=approvals,
    )

    task = await runtime.create_task("Write artifact")
    first = await runtime.run_until_blocked(task.task_id)

    assert first.task.state is TaskState.WAITING_APPROVAL
    assert first.approval_token
    assert effects == []
    request_id = first.task.active_step.approval_request_id
    assert request_id

    decision = approvals.decide(request_id, first.approval_token, "approve")
    assert decision.state is ApprovalState.APPROVED

    second = await runtime.run_until_blocked(task.task_id)
    assert second.task.state is TaskState.COMPLETED
    assert effects == ["a.txt"]

    replay = await runtime.run_until_blocked(task.task_id)
    assert replay.task.state is TaskState.COMPLETED
    assert effects == ["a.txt"]


@pytest.mark.asyncio
async def test_refusal_cancels_effect_without_execution() -> None:
    effects: list[str] = []
    approvals = ApprovalQueue()
    tools = ToolRegistry()
    tools.register(
        ToolSpec(
            name="deploy.production",
            description="Deploy production",
            risk=ToolRisk.HIGH_IMPACT,
            handler=lambda args: effects.append("deployed") or args,
            blast_radius="production",
        )
    )
    runtime = AgentRuntime(
        planner=StaticPlanner([step("deploy.production")]),
        tools=tools,
        approvals=approvals,
    )

    task = await runtime.create_task("Deploy")
    pending = await runtime.run_until_blocked(task.task_id)
    request_id = pending.task.active_step.approval_request_id
    assert request_id
    approvals.decide(request_id, pending.approval_token, "refuse")

    refused = await runtime.run_next(task.task_id)
    assert refused.task.state is TaskState.CANCELLED
    assert effects == []


@pytest.mark.asyncio
async def test_blocked_tool_fails_closed() -> None:
    tools = ToolRegistry()
    tools.register(
        ToolSpec(
            name="host.destroy",
            description="Never allowed",
            risk=ToolRisk.BLOCKED,
            handler=lambda args: "should not run",
        )
    )
    runtime = AgentRuntime(
        planner=StaticPlanner([step("host.destroy")]),
        tools=tools,
    )
    task = await runtime.create_task("Destroy host")

    result = await runtime.run_next(task.task_id)
    assert result.task.state is TaskState.FAILED
    assert "blocked tool" in result.task.failure_reason


@pytest.mark.asyncio
async def test_read_checkpoint_can_rewind_agent_state() -> None:
    calls: list[int] = []
    tools = ToolRegistry()
    tools.register(
        ToolSpec(
            name="read.counter",
            description="Read a counter",
            risk=ToolRisk.READ,
            handler=lambda args: calls.append(1) or "one",
        )
    )
    planner = StaticPlanner(
        [
            PlanStep("STEP-01", "Read one", ToolCall("read.counter")),
            PlanStep("STEP-02", "Read two", ToolCall("read.counter")),
        ]
    )
    runtime = AgentRuntime(planner=planner, tools=tools)
    task = await runtime.create_task("Read twice")

    first = await runtime.run_next(task.task_id)
    checkpoint_id = first.task.checkpoints[0].checkpoint_id
    assert first.task.current_step == 1

    rewound = runtime.rollback_agent_state(task.task_id, checkpoint_id)
    assert rewound.current_step == 0
    assert rewound.observations == []
    assert rewound.plan.steps[0].state is StepState.PLANNED


@pytest.mark.asyncio
async def test_agent_state_rollback_refuses_to_hide_external_effect() -> None:
    approvals = ApprovalQueue()
    tools = ToolRegistry()
    tools.register(
        ToolSpec(
            name="write.effect",
            description="Effectful action",
            risk=ToolRisk.WRITE,
            handler=lambda args: "done",
        )
    )
    runtime = AgentRuntime(
        planner=StaticPlanner([step("write.effect")]),
        tools=tools,
        approvals=approvals,
    )
    task = await runtime.create_task("Effect")
    pending = await runtime.run_next(task.task_id)
    checkpoint_id = pending.task.checkpoints[0].checkpoint_id
    request_id = pending.task.active_step.approval_request_id
    approvals.decide(request_id, pending.approval_token, "approve")
    completed = await runtime.run_next(task.task_id)
    assert completed.task.state is TaskState.COMPLETED

    with pytest.raises(AgentRuntimeError, match="cannot undo an external effect"):
        runtime.rollback_agent_state(task.task_id, checkpoint_id)


def test_learning_store_is_transparent_and_versioned() -> None:
    learning = InMemoryLearningStore()
    memory = learning.remember(
        "EditForge deployment work belongs to Systems",
        tags=["editforge", "systems"],
    )
    assert learning.search_memories("EditForge Systems")[0].memory_id == memory.memory_id

    first = learning.upsert_skill("repo audit", "Audit a repo", "Inspect tests and status")
    second = learning.upsert_skill("repo audit", "Audit a repo", "Inspect, test, then report")
    assert first.version == 1
    assert second.version == 2
    assert learning.get_skill("repo-audit").instructions == "Inspect, test, then report"
    assert learning.forget(memory.memory_id) is True
    assert learning.list_memories() == []


class JsonPlannerProvider(AIProvider):
    name = "json-test"

    def __init__(self, text: str) -> None:
        super().__init__(default_model="json-test", max_retries=0)
        self.text = text

    async def _complete_once(self, request: CompletionRequest) -> CompletionResponse:
        del request
        return CompletionResponse(
            text=self.text,
            usage=TokenUsage(),
            model="json-test",
            provider=self.name,
        )


@pytest.mark.asyncio
async def test_llm_planner_accepts_only_registered_tools() -> None:
    tools = ToolRegistry()
    tools.register(
        ToolSpec(
            name="repo.inspect",
            description="Inspect",
            risk=ToolRisk.READ,
            handler=lambda args: "ok",
        )
    )
    provider = JsonPlannerProvider(
        '{"steps":[{"title":"Inspect","tool":"repo.inspect","arguments":{},'
        '"reason":"need evidence","expected_outcome":"status"}],'
        '"completion_criteria":["status captured"]}'
    )
    planner = LLMPlanner(provider)

    plan = await planner.plan("Inspect Meta", {}, tools)
    assert plan.steps[0].tool_call.name == "repo.inspect"

    bad_provider = JsonPlannerProvider(
        '{"steps":[{"title":"Invent","tool":"made.up","arguments":{},'
        '"reason":"","expected_outcome":""}],"completion_criteria":[]}'
    )
    with pytest.raises(KeyError, match="unknown tool"):
        await LLMPlanner(bad_provider).plan("Do it", {}, tools)


# ---------------------------------------------------------------------------
# Soul recall at the planning seam
# ---------------------------------------------------------------------------

SOUL_TEE_HOST = "https://tee-soul-layer-test.svc.example.pinecone.io"
SOUL_DEVON_HOST = "https://devon-soul-test.svc.example.pinecone.io"


class RecordingPlanner(StaticPlanner):
    """StaticPlanner that keeps the context it was handed."""

    def __init__(self, steps) -> None:
        super().__init__(steps)
        self.seen_context = None

    async def plan(self, goal, context, tools):
        self.seen_context = dict(context)
        return await super().plan(goal, context, tools)


def _read_tools() -> ToolRegistry:
    tools = ToolRegistry()
    tools.register(
        ToolSpec(
            name="repo.inspect",
            description="Inspect repository state",
            risk=ToolRisk.READ,
            handler=lambda args: "ok",
        )
    )
    return tools


def _soul(handler) -> SoulLayer:
    return SoulLayer(
        api_key="pc-test-key",
        tee_host=SOUL_TEE_HOST,
        devon_host=SOUL_DEVON_HOST,
        transport=httpx.MockTransport(handler),
    )


@pytest.mark.asyncio
async def test_soul_recall_reaches_the_planner_with_framing_and_order() -> None:
    """Recall lands in the planner payload; framing and hierarchy survive."""

    def handler(request):
        if "tee-soul-layer" in str(request.url):
            hits = [
                {
                    "_id": "t1",
                    "_score": 0.10,
                    "fields": {"text": "the ruling", "ruled_on": "2026-08-20"},
                }
            ]
        else:
            hits = [
                {
                    "_id": "d1",
                    "_score": 0.99,
                    "fields": {"text": "the pattern", "observed_on": "2026-08-21"},
                }
            ]
        return httpx.Response(200, json={"result": {"hits": hits}})

    planner = RecordingPlanner([step("repo.inspect")])
    runtime = AgentRuntime(planner=planner, tools=_read_tools(), soul=_soul(handler))

    task = await runtime.create_task("Ship the release")
    payload = task.context["soul_recall"]

    assert payload["context"].startswith(CONTEXT_NOT_COMMAND)
    # Tee precedes DEVON in records and rendered context despite the scores.
    assert [r["source"] for r in payload["records"]] == ["tee-soul-layer", "devon-soul"]
    assert payload["context"].index("the ruling") < payload["context"].index("the pattern")
    assert payload["errors"] == []
    # The planner saw the same payload — recall informed the frozen plan.
    assert planner.seen_context["soul_recall"] == payload


@pytest.mark.asyncio
async def test_partial_soul_recall_surfaces_errors_never_looks_empty() -> None:
    def handler(request):
        if "tee-soul-layer" in str(request.url):
            return httpx.Response(
                200,
                json={
                    "result": {
                        "hits": [
                            {"_id": "t1", "_score": 0.8, "fields": {"text": "still here"}}
                        ]
                    }
                },
            )
        return httpx.Response(500, text="index melting")

    runtime = AgentRuntime(
        planner=StaticPlanner([step("repo.inspect")]),
        tools=_read_tools(),
        soul=_soul(handler),
    )

    task = await runtime.create_task("Anything")
    payload = task.context["soul_recall"]
    assert [r["source"] for r in payload["records"]] == ["tee-soul-layer"]
    assert payload["errors"] and "devon-soul unavailable" in payload["errors"][0]
    # The rendered context names the partial failure too.
    assert "Recall was partial" in payload["context"]


@pytest.mark.asyncio
async def test_soul_outage_degrades_to_planning_without_recall() -> None:
    """A dead provider must not break task creation — it lands in errors."""

    class ExplodingSoul:
        async def recall(self, text):
            raise RuntimeError("pinecone is down")

    runtime = AgentRuntime(
        planner=StaticPlanner([step("repo.inspect")]),
        tools=_read_tools(),
        soul=ExplodingSoul(),
    )

    task = await runtime.create_task("Anything")
    payload = task.context["soul_recall"]
    assert payload["records"] == []
    assert payload["context"] == ""
    assert payload["errors"] == ["soul recall unavailable: pinecone is down"]

    result = await runtime.run_until_blocked(task.task_id)
    assert result.task.state is TaskState.COMPLETED


@pytest.mark.asyncio
async def test_no_soul_means_no_soul_recall_key() -> None:
    runtime = AgentRuntime(
        planner=StaticPlanner([step("repo.inspect")]),
        tools=_read_tools(),
    )
    task = await runtime.create_task("Anything")
    assert "soul_recall" not in task.context

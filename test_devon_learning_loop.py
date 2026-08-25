"""Offline tests for Hermes learning-loop helpers."""

from services.agent_runtime.contracts import (
    AgentPlan,
    AgentTask,
    Observation,
    PlanStep,
    TaskState,
    ToolCall,
)
from services.agent_runtime.learning_loop import draft_skill_proposal_from_task


def _completed_task() -> AgentTask:
    task = AgentTask(
        task_id="TASK-OK",
        goal="File a receipt",
        context={},
        plan=AgentPlan(
            goal="File a receipt",
            steps=[
                PlanStep(
                    step_id="STEP-01",
                    title="Ask",
                    tool_call=ToolCall(name="operator.read", arguments={}),
                )
            ],
        ),
        state=TaskState.COMPLETED,
    )
    task.observations.append(
        Observation(step_id="STEP-01", ok=True, output="Asked for area")
    )
    return task


def test_draft_skill_proposal_from_completed_task() -> None:
    proposal = draft_skill_proposal_from_task(_completed_task())
    assert proposal is not None
    assert proposal.source_task_id == "TASK-OK"
    assert proposal.state.value == "proposed"
    assert "Asked for area" in proposal.instructions


def test_draft_skill_proposal_skips_incomplete_task() -> None:
    task = _completed_task()
    task.state = TaskState.RUNNING
    assert draft_skill_proposal_from_task(task) is None

"""
Workflow definition + engine tests — the services layer, no database.

Two behaviors are load-bearing and get the most attention:

- a definition that could resolve to nothing at run time is rejected at save
  time (forward references, unknown steps, malformed config);
- an effect step never executes without an explicit approval, and rejecting
  one halts the run rather than skipping the step.
"""

import pytest

from services.workflows import (
    RunStatus,
    StepOutput,
    StepStatus,
    StepType,
    WorkflowDefinition,
    WorkflowDefinitionError,
    WorkflowEngine,
    render_template,
)

READ_ONLY = {
    "version": 1,
    "trigger": {"type": "manual", "config": {}},
    "steps": [
        {
            "id": "recall",
            "type": "knowledge_search",
            "config": {"query": "{{ input }}", "limit": 4},
        },
        {
            "id": "council",
            "type": "council",
            "config": {"prompt": "Assess {{ input }} against {{ recall }}"},
        },
    ],
}

WITH_EFFECT = {
    "version": 1,
    "trigger": {"type": "manual", "config": {}},
    "steps": [
        {
            "id": "recall",
            "type": "knowledge_search",
            "config": {"query": "{{ input }}", "limit": 4},
        },
        {
            "id": "remember",
            "type": "memory_write",
            "config": {"content": "Learned: {{ recall }}", "importance": 7},
        },
        {
            "id": "brief",
            "type": "export",
            "config": {"title": "Risk brief", "body": "{{ remember }}"},
        },
    ],
}


def _handlers(record=None):
    """Handlers that echo their rendered config and note that they ran."""

    async def handler(ctx):
        if record is not None:
            record.append(ctx.step.id)
        return StepOutput(
            summary=f"{ctx.step.id}:ok",
            text=str(ctx.config),
            input_tokens=10,
            output_tokens=5,
        )

    return {step_type: handler for step_type in StepType}


# ---------------------------------------------------------------------------
# Definitions
# ---------------------------------------------------------------------------


def test_valid_definition_round_trips():
    definition = WorkflowDefinition.from_dict(WITH_EFFECT)
    assert [s.id for s in definition.steps] == ["recall", "remember", "brief"]
    assert [s.id for s in definition.effect_steps] == ["remember", "brief"]
    assert definition.to_dict() == WITH_EFFECT


def test_reads_are_not_effects():
    definition = WorkflowDefinition.from_dict(READ_ONLY)
    assert definition.effect_steps == []


def test_forward_reference_is_rejected():
    broken = {
        "version": 1,
        "trigger": {"type": "manual"},
        "steps": [
            {
                "id": "council",
                "type": "council",
                "config": {"prompt": "{{ recall }}"},
            },
            {
                "id": "recall",
                "type": "knowledge_search",
                "config": {"query": "{{ input }}"},
            },
        ],
    }
    with pytest.raises(WorkflowDefinitionError, match="not available yet"):
        WorkflowDefinition.from_dict(broken)


def test_unknown_field_on_a_step_reference_is_rejected():
    broken = {
        "version": 1,
        "trigger": {"type": "manual"},
        "steps": [
            {"id": "a", "type": "knowledge_search", "config": {"query": "x"}},
            {"id": "b", "type": "council", "config": {"prompt": "{{ a.nope }}"}},
        ],
    }
    with pytest.raises(WorkflowDefinitionError, match="unknown field"):
        WorkflowDefinition.from_dict(broken)


def test_duplicate_step_ids_are_rejected():
    broken = {
        "version": 1,
        "trigger": {"type": "manual"},
        "steps": [
            {"id": "a", "type": "knowledge_search", "config": {"query": "x"}},
            {"id": "a", "type": "council", "config": {"prompt": "y"}},
        ],
    }
    with pytest.raises(WorkflowDefinitionError, match="Duplicate step id"):
        WorkflowDefinition.from_dict(broken)


def test_missing_required_config_is_rejected():
    broken = {
        "version": 1,
        "trigger": {"type": "manual"},
        "steps": [{"id": "a", "type": "memory_write", "config": {"importance": 3}}],
    }
    with pytest.raises(WorkflowDefinitionError, match="requires a non-empty `content`"):
        WorkflowDefinition.from_dict(broken)


def test_out_of_range_config_is_rejected():
    broken = {
        "version": 1,
        "trigger": {"type": "manual"},
        "steps": [
            {"id": "a", "type": "knowledge_search", "config": {"query": "x", "limit": 99}}
        ],
    }
    with pytest.raises(WorkflowDefinitionError, match="between 1 and 20"):
        WorkflowDefinition.from_dict(broken)


def test_step_ceiling_is_enforced():
    steps = [
        {"id": f"s{i}", "type": "knowledge_search", "config": {"query": "x"}}
        for i in range(5)
    ]
    with pytest.raises(WorkflowDefinitionError, match="at most 3 steps"):
        WorkflowDefinition.from_dict(
            {"version": 1, "trigger": {"type": "manual"}, "steps": steps}, max_steps=3
        )


def test_schedule_trigger_needs_a_cadence():
    with pytest.raises(WorkflowDefinitionError, match="cadence"):
        WorkflowDefinition.from_dict(
            {"version": 1, "trigger": {"type": "schedule", "config": {}}, "steps": []}
        )


def test_non_manual_triggers_report_that_nothing_dispatches_them():
    scheduled = WorkflowDefinition.from_dict(
        {
            "version": 1,
            "trigger": {"type": "schedule", "config": {"cadence": "weekly"}},
            "steps": [],
        }
    )
    manual = WorkflowDefinition.from_dict(READ_ONLY)
    assert scheduled.trigger.awaiting_dispatcher is True
    assert manual.trigger.awaiting_dispatcher is False


def test_unsupported_version_is_rejected():
    with pytest.raises(WorkflowDefinitionError, match="Unsupported definition version"):
        WorkflowDefinition.from_dict({"version": 99, "trigger": {}, "steps": []})


def test_render_template_resolves_input_and_earlier_steps():
    rendered = render_template(
        {"a": "{{ input }}", "b": ["{{ recall.text }}", "{{ recall }}"]},
        trigger_input="pricing",
        results={"recall": {"summary": "short", "text": "long"}},
    )
    assert rendered == {"a": "pricing", "b": ["long", "short"]}


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


async def test_read_only_workflow_runs_unattended():
    ran = []
    outcome = await WorkflowEngine(_handlers(ran)).run(
        WorkflowDefinition.from_dict(READ_ONLY), trigger_input="pricing"
    )
    assert outcome.status == RunStatus.COMPLETED
    assert ran == ["recall", "council"]
    assert outcome.total_tokens == 30


async def test_engine_stops_in_front_of_the_first_effect():
    ran = []
    outcome = await WorkflowEngine(_handlers(ran)).run(
        WorkflowDefinition.from_dict(WITH_EFFECT), trigger_input="pricing"
    )
    assert outcome.status == RunStatus.AWAITING_APPROVAL
    assert outcome.pending_step_id == "remember"
    assert ran == ["recall"]
    assert outcome.is_terminal is False


async def test_the_gate_previews_the_rendered_text_not_the_template():
    events = []
    await WorkflowEngine(_handlers()).run(
        WorkflowDefinition.from_dict(WITH_EFFECT),
        trigger_input="pricing",
        on_event=events.append,
    )
    gate = next(e for e in events if e["type"] == "awaiting_approval")
    assert gate["preview"]["content"] == "Learned: recall:ok"


async def test_approval_resumes_without_rerunning_completed_steps():
    ran = []
    engine = WorkflowEngine(_handlers(ran))
    definition = WorkflowDefinition.from_dict(WITH_EFFECT)

    first = await engine.run(definition, trigger_input="pricing")
    ran.clear()

    second = await engine.run(
        definition,
        trigger_input="pricing",
        prior_results=first.results_as_dicts(),
        approvals={"remember": "approved"},
    )
    assert second.status == RunStatus.AWAITING_APPROVAL
    assert second.pending_step_id == "brief"
    assert ran == ["remember"]  # recall was not run a second time

    third = await engine.run(
        definition,
        trigger_input="pricing",
        prior_results=second.results_as_dicts(),
        approvals={"remember": "approved", "brief": "approved"},
    )
    assert third.status == RunStatus.COMPLETED
    assert [r.step_id for r in third.results] == ["recall", "remember", "brief"]


async def test_rejection_halts_the_run_and_records_the_refusal():
    ran = []
    engine = WorkflowEngine(_handlers(ran))
    definition = WorkflowDefinition.from_dict(WITH_EFFECT)

    first = await engine.run(definition, trigger_input="pricing")
    ran.clear()

    outcome = await engine.run(
        definition,
        trigger_input="pricing",
        prior_results=first.results_as_dicts(),
        approvals={"remember": "rejected"},
    )
    assert outcome.status == RunStatus.HALTED
    assert ran == []
    rejected = outcome.results[-1]
    assert rejected.step_id == "remember"
    assert rejected.status == StepStatus.REJECTED
    assert "brief" not in [r.step_id for r in outcome.results]


async def test_effects_still_wait_when_a_later_step_is_pre_approved():
    """Approving step 3 does not let step 2 through."""
    outcome = await WorkflowEngine(_handlers()).run(
        WorkflowDefinition.from_dict(WITH_EFFECT),
        trigger_input="pricing",
        approvals={"brief": "approved"},
    )
    assert outcome.status == RunStatus.AWAITING_APPROVAL
    assert outcome.pending_step_id == "remember"


async def test_handler_failure_is_recorded_not_swallowed():
    async def explode(ctx):
        raise RuntimeError("provider unavailable")

    handlers = _handlers()
    handlers[StepType.KNOWLEDGE_SEARCH] = explode

    outcome = await WorkflowEngine(handlers).run(
        WorkflowDefinition.from_dict(READ_ONLY), trigger_input="pricing"
    )
    assert outcome.status == RunStatus.FAILED
    assert outcome.error == "RuntimeError: provider unavailable"
    assert outcome.results[-1].status == StepStatus.FAILED


async def test_missing_handler_fails_loudly():
    handlers = _handlers()
    del handlers[StepType.COUNCIL]
    outcome = await WorkflowEngine(handlers).run(
        WorkflowDefinition.from_dict(READ_ONLY), trigger_input="pricing"
    )
    assert outcome.status == RunStatus.FAILED
    assert "No handler registered" in (outcome.error or "")


async def test_empty_workflow_fails_rather_than_reporting_success():
    outcome = await WorkflowEngine(_handlers()).run(WorkflowDefinition.empty())
    assert outcome.status == RunStatus.FAILED
    assert outcome.results == []


async def test_approval_can_be_disabled_only_in_process():
    """The flag exists for tests; nothing in the API can reach it."""
    outcome = await WorkflowEngine(
        _handlers(), require_approval_for_effects=False
    ).run(WorkflowDefinition.from_dict(WITH_EFFECT), trigger_input="pricing")
    assert outcome.status == RunStatus.COMPLETED
    assert len(outcome.results) == 3


async def test_token_usage_is_summed_across_steps():
    outcome = await WorkflowEngine(
        _handlers(), require_approval_for_effects=False
    ).run(WorkflowDefinition.from_dict(WITH_EFFECT))
    assert outcome.token_usage() == {
        "input_tokens": 30,
        "output_tokens": 15,
        "total_tokens": 45,
    }

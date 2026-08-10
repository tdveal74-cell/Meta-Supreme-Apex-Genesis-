"""Workflow definition validation — pure unit tests, no database."""

import pytest

from definition import (
    EFFECT_STEP_TYPES,
    StepType,
    WorkflowDefinition,
    WorkflowDefinitionError,
    render_template,
)


def test_empty_definition():
    d = WorkflowDefinition.empty()
    assert d.steps == []
    assert d.trigger.type.value == "manual"


def test_valid_council_then_memory_requires_approval_gate():
    raw = {
        "version": 1,
        "trigger": {"type": "manual", "config": {}},
        "steps": [
            {
                "id": "council",
                "type": "council",
                "config": {"prompt": "Assess: {{ input }}", "full_council": True},
            },
            {
                "id": "remember",
                "type": "memory_write",
                "config": {"content": "{{ council }}", "importance": 6},
            },
        ],
    }
    d = WorkflowDefinition.from_dict(raw)
    assert len(d.steps) == 2
    assert d.effect_steps[0].id == "remember"
    assert StepType.MEMORY_WRITE in EFFECT_STEP_TYPES


def test_forward_reference_rejected():
    raw = {
        "version": 1,
        "trigger": {"type": "manual"},
        "steps": [
            {
                "id": "early",
                "type": "memory_write",
                "config": {"content": "{{ later }}"},
            },
            {
                "id": "later",
                "type": "council",
                "config": {"prompt": "{{ input }}"},
            },
        ],
    }
    with pytest.raises(WorkflowDefinitionError):
        WorkflowDefinition.from_dict(raw)


def test_schedule_needs_cadence():
    raw = {
        "version": 1,
        "trigger": {"type": "schedule", "config": {}},
        "steps": [],
    }
    with pytest.raises(WorkflowDefinitionError):
        WorkflowDefinition.from_dict(raw)


def test_render_template_input_and_step():
    out = render_template(
        "Q: {{ input }} / A: {{ council.summary }}",
        trigger_input="Should we ship?",
        results={"council": {"summary": "Proceed with conditions"}},
    )
    assert "Should we ship?" in out
    assert "Proceed with conditions" in out

"""The DEVON ecosystem doctrine, checked against the diagram it was compiled from.

These are pure tests: no database, no network, no application import. They are
the ones worth running everywhere, and they are what the ledger writer relies on
being true.
"""

from __future__ import annotations

import pytest

from services.devon import areas, ecosystem
from services.devon.operating_layer import Surface

# ---------------------------------------------------------------------------
# Authority
# ---------------------------------------------------------------------------

def test_the_hierarchy_is_the_diagram_line_in_order():
    assert [a.name for a in ecosystem.HIERARCHY] == [
        "TEE",
        "TEE_SOUL",
        "DEVON",
        "COUNCIL",
        "AUTOMATION",
        "TOOLS",
    ]
    assert ecosystem.HIERARCHY_LINE == "TEE > TEE SOUL > DEVON > COUNCIL > AUTOMATION > TOOLS"


def test_the_council_stays_under_devon_per_tees_ruling():
    assert ecosystem.outranks(ecosystem.Authority.DEVON, ecosystem.Authority.COUNCIL)
    assert not ecosystem.outranks(ecosystem.Authority.COUNCIL, ecosystem.Authority.DEVON)
    allowed, reason = ecosystem.may_override(
        ecosystem.Authority.COUNCIL, ecosystem.Authority.DEVON
    )
    assert not allowed
    assert "ranks below" in reason


def test_nothing_overrides_itself_and_tee_overrides_everything():
    refused, reason = ecosystem.may_override(
        ecosystem.Authority.DEVON, ecosystem.Authority.DEVON
    )
    assert not refused
    assert "does not override itself" in reason
    for lower in ecosystem.HIERARCHY[1:]:
        allowed, _ = ecosystem.may_override(ecosystem.Authority.TEE, lower)
        assert allowed


# ---------------------------------------------------------------------------
# The mind
# ---------------------------------------------------------------------------

def test_the_mind_has_five_layers_numbered_one_to_five():
    assert [layer.number for layer in ecosystem.MIND_LAYERS] == [1, 2, 3, 4, 5]
    assert [layer.name for layer in ecosystem.MIND_LAYERS] == [
        "Tee Soul",
        "Devon Attention",
        "Devon Conscious",
        "Devon Subconscious",
        "Devon Soul",
    ]


def test_the_tee_soul_layer_refuses_every_write():
    allowed, reason = ecosystem.check_layer_write(1)
    assert not allowed
    assert "read only" in reason.lower()


def test_working_memory_is_rebuilt_not_written():
    for layer in (2, 3):
        allowed, reason = ecosystem.check_layer_write(layer)
        assert not allowed
        assert "rebuilt" in reason


def test_the_devon_soul_needs_a_ruling_and_the_subconscious_does_not():
    assert ecosystem.check_layer_write(4)[0]
    assert not ecosystem.check_layer_write(5)[0]
    assert ecosystem.check_layer_write(5, approved_by_tee=True)[0]


def test_an_unknown_layer_fails_closed():
    allowed, reason = ecosystem.check_layer_write(6)
    assert not allowed
    assert "five" in reason


def test_the_eight_tee_soul_facets_are_carried():
    assert len(ecosystem.TEE_SOUL_FACETS) == 8
    assert "Non-Negotiables" in ecosystem.TEE_SOUL_FACETS


# ---------------------------------------------------------------------------
# Intents
# ---------------------------------------------------------------------------

def test_every_input_becomes_one_uuid_intent():
    first = ecosystem.open_intent("chat/voice", "remember the callback")
    second = ecosystem.open_intent("chat/voice", "remember the callback")
    assert first.intent_id != second.intent_id
    assert len(first.intent_id) == 36
    assert first.channel == "chat_voice"


def test_an_unrecorded_channel_is_refused_by_name():
    with pytest.raises(ValueError, match="not a recorded input channel"):
        ecosystem.open_intent("carrier pigeon", "hello")


def test_an_empty_intent_cannot_be_opened():
    with pytest.raises(ValueError, match="cannot be acted on"):
        ecosystem.open_intent("email", "   ")


def test_the_six_channels_all_normalize():
    for channel in ecosystem.INPUT_CHANNELS:
        assert ecosystem.normalize_channel(channel) == channel


# ---------------------------------------------------------------------------
# The event bus
# ---------------------------------------------------------------------------

def test_there_are_exactly_thirteen_universal_events():
    assert len(ecosystem.EVENTS) == 13
    assert len(set(ecosystem.EVENTS)) == 13


def test_a_legal_run_passes_end_to_end():
    assert (
        ecosystem.check_event_sequence(
            [
                "INTENT_RECEIVED",
                "CONTEXT_LOADED",
                "SOUL_READ",
                "SUBCONSCIOUS_RECALLED",
                "PLAN_CREATED",
                "ACTION_STARTED",
                "ARTIFACT_CREATED",
                "ACTION_COMPLETED",
                "VERIFICATION_PASSED",
                "LEARNING_CAPTURED",
            ]
        )
        == []
    )


def test_a_run_that_does_not_open_with_intent_received_is_refused():
    violations = ecosystem.check_event_sequence(["CONTEXT_LOADED"])
    assert any("opens with INTENT_RECEIVED" in v for v in violations)


def test_an_empty_sequence_is_not_a_run():
    assert ecosystem.check_event_sequence([]) != []


def test_an_event_before_its_prerequisite_is_refused():
    violations = ecosystem.check_event_sequence(
        ["INTENT_RECEIVED", "ACTION_COMPLETED"]
    )
    assert any("ACTION_COMPLETED before ACTION_STARTED" in v for v in violations)


def test_an_unknown_event_name_is_refused():
    violations = ecosystem.check_event_sequence(["INTENT_RECEIVED", "SOMETHING_ELSE"])
    assert any("not one of the thirteen" in v for v in violations)


def test_an_intent_is_received_exactly_once():
    violations = ecosystem.check_event_sequence(["INTENT_RECEIVED", "INTENT_RECEIVED"])
    assert any("received once" in v for v in violations)


def test_an_effect_action_cannot_start_without_an_approval_on_the_record():
    unapproved = ["INTENT_RECEIVED", "CONTEXT_LOADED", "PLAN_CREATED", "ACTION_STARTED"]
    assert ecosystem.check_event_sequence(unapproved, effect=True) != []
    assert ecosystem.check_event_sequence(unapproved, effect=False) == []

    approved = [
        "INTENT_RECEIVED",
        "CONTEXT_LOADED",
        "PLAN_CREATED",
        "APPROVAL_REQUESTED",
        "APPROVAL_GRANTED",
        "ACTION_STARTED",
    ]
    assert ecosystem.check_event_sequence(approved, effect=True) == []


def test_the_emergency_stop_refuses_a_start_even_when_the_sequence_is_legal():
    seen = ["INTENT_RECEIVED", "CONTEXT_LOADED", "PLAN_CREATED"]
    assert ecosystem.check_event("ACTION_STARTED", seen) == []
    stopped = ecosystem.check_event("ACTION_STARTED", seen, emergency_stopped=True)
    assert any("Emergency stop is engaged" in v for v in stopped)


def test_next_legal_events_never_offers_an_illegal_one():
    seen = ["INTENT_RECEIVED", "CONTEXT_LOADED", "PLAN_CREATED"]
    for candidate in ecosystem.next_legal_events(seen, effect=True):
        assert ecosystem.check_event(candidate, seen, effect=True) == []
    assert "ACTION_STARTED" not in ecosystem.next_legal_events(seen, effect=True)
    assert "ACTION_STARTED" in ecosystem.next_legal_events(seen, effect=False)


def test_state_is_derived_from_events_and_a_failure_outranks_a_completion():
    assert ecosystem.derive_state([]) is ecosystem.IntentState.RECEIVED
    assert (
        ecosystem.derive_state(["INTENT_RECEIVED", "CONTEXT_LOADED", "PLAN_CREATED"])
        is ecosystem.IntentState.PLANNED
    )
    assert (
        ecosystem.derive_state(
            ["INTENT_RECEIVED", "CONTEXT_LOADED", "PLAN_CREATED", "APPROVAL_REQUESTED"]
        )
        is ecosystem.IntentState.AWAITING_APPROVAL
    )
    mixed = [
        "INTENT_RECEIVED",
        "CONTEXT_LOADED",
        "PLAN_CREATED",
        "ACTION_STARTED",
        "ACTION_COMPLETED",
        "ACTION_FAILED",
    ]
    assert ecosystem.derive_state(mixed) is ecosystem.IntentState.FAILED


# ---------------------------------------------------------------------------
# The universal receipt
# ---------------------------------------------------------------------------

def _receipt(**overrides) -> ecosystem.UniversalReceipt:
    base = {
        "intent_id": "11111111-1111-1111-1111-111111111111",
        "what_happened": "filed the capture",
        "verification": "read the row back at id 42",
        "provenance": "devon ledger writer",
    }
    base.update(overrides)
    return ecosystem.UniversalReceipt(**base)


def test_a_complete_receipt_stands():
    assert ecosystem.check_receipt(_receipt()) == []


def test_a_second_receipt_for_one_intent_is_refused():
    receipt = _receipt()
    failures = ecosystem.check_receipt(receipt, already_receipted=[receipt.intent_id])
    assert any("already holds its one receipt" in f for f in failures)


@pytest.mark.parametrize(
    "field", ["what_happened", "verification", "provenance", "intent_id"]
)
def test_every_required_receipt_field_is_required(field):
    failures = ecosystem.check_receipt(_receipt(**{field: "  "}))
    assert failures


def test_an_intent_that_reached_nothing_cannot_be_receipted():
    ok, reason = ecosystem.intent_is_receiptable(["INTENT_RECEIVED", "CONTEXT_LOADED"])
    assert not ok
    assert "terminal event" in reason


def test_an_intent_that_completed_can_be_receipted():
    ok, _ = ecosystem.intent_is_receiptable(
        ["INTENT_RECEIVED", "CONTEXT_LOADED", "PLAN_CREATED", "ACTION_STARTED", "ACTION_COMPLETED"]
    )
    assert ok


def test_an_effect_intent_that_skipped_its_gate_cannot_be_receipted():
    ok, reason = ecosystem.intent_is_receiptable(
        ["INTENT_RECEIVED", "CONTEXT_LOADED", "PLAN_CREATED", "ACTION_STARTED", "ACTION_COMPLETED"],
        effect=True,
    )
    assert not ok
    assert "APPROVAL_GRANTED" in reason


# ---------------------------------------------------------------------------
# Memory indexes
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "name", ["tee-soul-layer", "devon-soul", "devon-subconscious"]
)
def test_every_diagram_index_is_recorded_and_protected(name):
    index = ecosystem.MEMORY_INDEXES[name]
    assert index.protection.startswith("PROTECTED")
    assert ecosystem.deletion_protection_for(name) == "enabled"


@pytest.mark.parametrize(
    "name", ["tee-soul-layer", "devon-soul", "devon-subconscious", "something-else"]
)
def test_no_index_may_ever_be_deleted_by_automation(name):
    allowed, reason = ecosystem.may_delete_index(name)
    assert not allowed
    assert reason


def test_a_tee_soul_record_is_never_removed_and_a_devon_soul_record_needs_a_ruling():
    assert not ecosystem.may_delete_record("tee-soul-layer")[0]
    assert not ecosystem.may_delete_record("devon-soul")[0]
    assert ecosystem.may_delete_record("devon-soul", approved_by_tee=True)[0]
    assert ecosystem.may_delete_record("devon-subconscious")[0]


def test_the_vendor_setting_is_declared_once_and_used_by_the_soul_client():
    from services.intelligence import soul

    assert soul.DELETION_PROTECTION == ecosystem.VENDOR_DELETION_PROTECTION


# ---------------------------------------------------------------------------
# Execution layer
# ---------------------------------------------------------------------------

def test_internal_duties_go_to_n8n_and_external_duties_go_to_zapier():
    assert ecosystem.route_action("devon workflows")[0] == "n8n"
    assert ecosystem.route_action("soul ops")[0] == "n8n"
    assert ecosystem.route_action("external saas")[0] == "zapier"
    assert ecosystem.route_action("crm")[0] == "zapier"


def test_an_unrecognised_duty_is_parked_rather_than_guessed():
    executor, reason = ecosystem.route_action("teleport the thing")
    assert executor == ecosystem.UNROUTED
    assert "not a recorded duty" in reason


def test_the_two_executors_are_the_diagram_pair():
    assert set(ecosystem.EXECUTORS) == {"n8n", "zapier"}
    assert {e.value for e in ecosystem.Executor} == {"n8n", "zapier"}


def test_no_duty_is_claimed_by_both_executors():
    assert not set(ecosystem.N8N_DUTIES) & set(ecosystem.ZAPIER_DUTIES)


# ---------------------------------------------------------------------------
# Emergency stop
# ---------------------------------------------------------------------------

def test_only_tee_releases_the_emergency_stop():
    assert ecosystem.may_release_emergency_stop(ecosystem.Authority.TEE)[0]
    for actor in ecosystem.HIERARCHY[1:]:
        allowed, reason = ecosystem.may_release_emergency_stop(actor)
        assert not allowed
        assert "may engage" in reason


# ---------------------------------------------------------------------------
# Intelligence routing
# ---------------------------------------------------------------------------

def test_mechanical_work_goes_to_cerebras_and_judgement_to_the_council():
    assert ecosystem.route_thinking("classification")[0] == "cerebras"
    assert ecosystem.route_thinking("risk analysis")[0] == "council"


def test_an_unrecorded_thinking_duty_is_declined_rather_than_guessed():
    assert ecosystem.route_thinking("read my mind")[0] == "DECLINED"


def test_the_operating_surfaces_come_from_the_one_registry():
    assert ecosystem.OPERATING_SURFACES == tuple(s.value for s in Surface)


# ---------------------------------------------------------------------------
# Ledger shape, portfolio, and the map as a whole
# ---------------------------------------------------------------------------

def test_the_ledger_carries_the_ten_diagram_tables():
    assert ecosystem.LEDGER_TABLES == (
        "intents",
        "actions",
        "events",
        "approvals",
        "artifacts",
        "executors",
        "systems",
        "errors",
        "verifications",
        "learning_candidates",
    )


def test_the_ledger_never_becomes_a_second_approval_authority():
    assert "never grants" in ecosystem.LEDGER_APPROVAL_RULE


@pytest.mark.parametrize(
    "code,name",
    [
        ("TQO", "The Quiet Operator"),
        ("TSWS", "The Shadow We Share"),
        ("NCO", "NCO Forge"),
        ("ACX", "Ascension Caudex"),
    ],
)
def test_the_four_properties_stay_separate_and_resolve_through_the_area_registry(code, name):
    assert (code, name) in ecosystem.PORTFOLIO
    # areas.py owns the codes. This asserts the map never becomes a second
    # registry that can drift away from the one that files things.
    assert areas.normalize_code(code) in areas.canonical_codes()


def test_the_nine_security_guarantees_are_carried_including_emergency_stop():
    assert len(ecosystem.SECURITY_GUARANTEES) == 9
    assert "emergency stop" in ecosystem.SECURITY_GUARANTEES


def test_the_summary_is_json_shaped_and_names_the_whole_organism():
    import json

    payload = ecosystem.summary()
    json.dumps(payload)
    assert payload["motto"] == "One organism. One intent. One receipt."
    assert len(payload["events"]) == 13
    assert len(payload["mind_layers"]) == 5
    assert len(payload["portfolio"]) == 4
    assert payload["hierarchy"][0] == "TEE"
    assert set(payload["memory_indexes"]) == set(ecosystem.MEMORY_INDEXES)

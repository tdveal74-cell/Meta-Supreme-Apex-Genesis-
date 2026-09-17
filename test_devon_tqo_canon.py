"""
The show canon, checked against the node it was lifted from.

The load bearing test here is `test_every_rule_is_traceable_to_the_mirror`. A
canon written from memory beside a live prompt is a second source of truth that
drifts on the first edit nobody copies back, which is the exact failure
`n8n/tqo-v5/README.md` was created to stop. So every rule carries a distinctive
phrase that must still appear in the mirrored node source, and the canon fails
the build when the mirror moves without it.

The dash finding is tested as a working detector driven over known good and
known bad input, not by pinning the live count. Pinning it would make this file
fail the day Tee fixes the live node, which is backwards.
"""

from __future__ import annotations

import pytest

from services.devon.rule_ledger import (
    AssemblyRefused,
    RuleClass,
    check_assembly,
    require_assembly,
)
from services.devon.tqo_canon import (
    BANNED_MARKS,
    COMPLIANCE,
    CRAFT,
    MEASURED_CHARS,
    MEASURED_WORDS,
    banned_marks,
    ledger,
    mirror_text,
)

#: One distinctive phrase per rule, each of which must still be present in the
#: mirrored node. Short enough to survive a reflow, long enough that a match is
#: not a coincidence.
TRACES = {
    "compliance.owned-presenter": "his own likeness and his own cloned voice",
    "compliance.no-stolen-valor": "never invents named operations",
    "compliance.no-combat-violence-footage": "realistic combat violence",
    "tqo.hook.first-fifteen-seconds": "decide whether this video is watched or skipped",
    "tqo.voice.calm-register": "Calm is the weapon",
    "tqo.length.1200-2000": "hard floor 1200",
    "tqo.broll.cutaways-not-people": "no anonymous professionals at desks",
    "tqo.close.one-quiet-cta": "the brand does not beg",
    "tqo.format.pick-one": "CONTRARIAN",
    "tqo.keyword.primary": "Never keyword-stuff",
    "tqo.frame.outcomes-not-topics": "FRAME OUTCOMES, NOT TOPICS",
    "nco.voice.seasoned-nco": "Concrete examples over abstract principles",
    "nco.pillars.pick-one": "THE FIVE PILLARS",
    "nco.benefits.verify-do-not-guess": "verify with your transition counselor",
    "nco.never-pain-as-coping": "Never present discomfort or pain as a coping technique",
}

#: Compliance rules whose text comes from the QC gate rather than the script
#: prompt, so they are traced to that mirror instead.
QC_TRACES = {
    "compliance.sourced-claims": "studies show",
    "compliance.crisis-support-resource": "support resource named on screen",
    "compliance.no-named-person-negative": "names a real identifiable person in a negative light",
    "compliance.no-banned-dashes": "no em dashes and no en dashes anywhere",
}


def qc_text() -> str:
    from services.devon.tqo_canon import MIRROR

    return (MIRROR.parent / "build_qc_prompt.js").read_text(encoding="utf-8")


def test_the_mirror_is_present_and_is_the_real_node():
    text = mirror_text()
    assert "Build Script Prompt" in text
    assert "Show Context: Script" in text
    assert len(text) > 9000, "the mirror is too short to be the node that was read"


def test_every_rule_is_traceable_to_the_mirror():
    """A canon that stops matching its source is drift, and drift fails here."""
    book = ledger()
    script, qc = mirror_text(), qc_text()

    covered = set(TRACES) | set(QC_TRACES)
    ids = {rule.id for rule in book.rules}
    assert covered == ids, (
        "every rule needs a trace phrase; untraced: "
        f"{sorted(ids - covered)}, stale: {sorted(covered - ids)}"
    )

    for rule_id, phrase in TRACES.items():
        assert phrase in script, f"{rule_id}: '{phrase}' is no longer in the script prompt mirror"
    for rule_id, phrase in QC_TRACES.items():
        assert phrase in qc, f"{rule_id}: '{phrase}' is no longer in the QC prompt mirror"


def test_a_trace_phrase_that_is_absent_actually_fails():
    """Anti vacuity: the check above must be able to fail."""
    assert "a phrase that is certainly not in the node" not in mirror_text()


def test_the_measurements_match_the_mirror():
    """The four thousand word figure was the teardown's whole cost argument.

    Counted here from the artifact so the number in the docstring cannot rot.
    """
    text = mirror_text()
    blocks = text.split("system = `")
    assert len(blocks) == 3, "expected exactly two template literals assigned to system"
    nco = blocks[1].split("`;")[0]
    tqo = blocks[2].split("`;")[0]

    assert len(tqo.split()) == MEASURED_WORDS["tqo"]
    assert len(nco.split()) == MEASURED_WORDS["nco"]
    assert len(tqo) == MEASURED_CHARS["tqo"]
    assert len(nco) == MEASURED_CHARS["nco"]
    assert MEASURED_WORDS["tqo"] < 1000, "the canon is not four thousand words"


def test_compliance_rules_do_not_bend_and_carry_no_scope():
    for rule in COMPLIANCE:
        assert rule.rule_class is RuleClass.COMPLIANCE
        assert rule.bends == ()
        assert rule.scope == ()
        assert rule.bends_under(["deadline", "correction episode", "anything"]) == ()


def test_every_craft_rule_declares_a_scope_this_estate_recognises():
    for rule in CRAFT:
        assert rule.rule_class is RuleClass.CRAFT
        assert rule.scope, f"{rule.id} would ship on every assembly"
        assert set(rule.scope_keys) <= {"tqo", "nco"}, rule.id


def test_the_two_shows_get_different_craft_and_the_same_compliance():
    book = ledger()
    tqo = book.assemble(scopes=["tqo"])
    nco = book.assemble(scopes=["nco"])

    assert {r.id for r in tqo.compliance} == {r.id for r in nco.compliance}

    tqo_only = {r.id for r in tqo.craft} - {r.id for r in nco.craft}
    nco_only = {r.id for r in nco.craft} - {r.id for r in tqo.craft}
    assert "tqo.voice.calm-register" in tqo_only
    assert "nco.voice.seasoned-nco" in nco_only
    assert "tqo.length.1200-2000" in {r.id for r in tqo.craft}
    assert "tqo.length.1200-2000" in {r.id for r in nco.craft}, "shared rule must appear in both"


def test_an_assembly_that_lost_the_presenter_rule_is_refused():
    """The rule that keeps Tee's own likeness on screen is compliance grade."""
    book = ledger()
    full = book.assemble(scopes=["tqo"])
    stripped = type(full)(
        rules=tuple(r for r in full.rules if r.id != "compliance.owned-presenter"),
        scopes=("tqo",),
    )
    check = check_assembly(stripped, book, min_chars=0)
    assert check.ok is False
    assert any("compliance.owned-presenter" in reason for reason in check.reasons)
    with pytest.raises(AssemblyRefused):
        require_assembly(stripped, book, min_chars=0)


def test_a_real_assembly_clears_the_measured_floor():
    book = ledger()
    for show in ("tqo", "nco"):
        assembled = book.assemble(scopes=[show])
        body = assembled.text()
        assert require_assembly(assembled, book, min_chars=len(body)) is assembled
        assert check_assembly(assembled, book, min_chars=len(body) + 1).ok is False


def test_the_length_rule_bends_because_the_lane_expands_rather_than_refuses():
    rule = ledger().by_id("tqo.length.1200-2000")
    assert rule is not None
    assert rule.bends_under([]) == ()
    fired = rule.bends_under(["script below the floor"])
    assert len(fired) == 1
    assert "Expand Script" in fired[0].instead
    assert "Script: Still Short?" in fired[0].evidence


def test_the_banned_mark_detector_works_both_ways():
    good = "A clean line, with a hyphen-joined word and nothing banned."
    assert banned_marks(good) == ()
    bad = "a line carrying " + BANNED_MARKS[0] + " a banned mark"
    assert len(banned_marks(bad)) == 1
    assert len(banned_marks(good + "\n" + bad)) == 1


def test_the_live_mirror_currently_violates_the_dash_rule():
    """The finding, stated as a measurement rather than a pinned count.

    The NCO branch instructs the model to emit a description line carrying a
    banned mark, while hard rule 1 bans it studio wide and the QC gate caps the
    voice dimension at 3 for any occurrence. Asserting only that at least one
    exists keeps this test honest without failing the day it is fixed: when the
    node is clean this flips to zero and the assertion below is the one to
    delete, deliberately, in the same change.
    """
    hits = banned_marks(mirror_text())
    assert len(hits) >= 1
    assert any("NCO Forge" in line for line in hits), (
        "the description line is the one that reaches an audience"
    )


def test_the_ledger_reports_how_much_of_the_canon_is_still_absolute():
    book = ledger()
    unqualified = book.unqualified()
    assert len(unqualified) >= 1
    assert all(r.rule_class is RuleClass.CRAFT for r in unqualified)
    assert "tqo.length.1200-2000" not in {r.id for r in unqualified}

"""
The exception layer, tested against the failures it exists to prevent.

Two of these matter more than the rest. `test_a_compliance_rule_never_bends`
drives conditions at a compliance rule that would fire every bend a craft rule
has, and asserts nothing comes back. `test_an_assembly_missing_a_compliance_
rule_is_refused` builds the assembly by hand, the way a real scoping bug would,
rather than through the constructor that cannot produce it, because a guard
tested only against input its own code generated proves nothing.
"""

from __future__ import annotations

import pytest

from services.devon.rule_ledger import (
    UNCONDITIONAL_DOMAINS,
    Assembly,
    AssemblyRefused,
    Bend,
    Rule,
    RuleClass,
    RuleError,
    RuleLedger,
    check_assembly,
    require_assembly,
)


def disclosure() -> Rule:
    return Rule(
        id="compliance.ai-disclosure",
        text="Every published episode discloses that AI was used to produce it.",
        rule_class=RuleClass.COMPLIANCE,
    )


def identity() -> Rule:
    return Rule(
        id="compliance.channel-identity",
        text="The presenter is Tee's own likeness and cloned voice. Never a rented persona.",
        rule_class=RuleClass.COMPLIANCE,
    )


def hook() -> Rule:
    return Rule(
        id="tqo.hook.learning-objective",
        text="State the Learning Objective inside the first 30 seconds.",
        rule_class=RuleClass.CRAFT,
        scope=("tqo", "teaching"),
        confidence=0.9,
        bends=(
            Bend(
                condition="correction episode",
                instead="Open on what the earlier episode got wrong, then the objective.",
                evidence="TQO correction cut, 2026-09-08 review, the objective read as evasive",
            ),
        ),
    )


def ledger() -> RuleLedger:
    return RuleLedger(rules=(disclosure(), identity(), hook()))


def test_the_unconditional_domains_are_the_ones_tee_named():
    assert "AI disclosure" in UNCONDITIONAL_DOMAINS
    assert "authorship" in UNCONDITIONAL_DOMAINS
    assert "rights" in UNCONDITIONAL_DOMAINS
    assert "channel identity" in UNCONDITIONAL_DOMAINS
    assert "platform policy" in UNCONDITIONAL_DOMAINS


def test_a_compliance_rule_cannot_carry_an_exception():
    with pytest.raises(RuleError) as caught:
        Rule(
            id="compliance.rights",
            text="Licensed footage only.",
            rule_class=RuleClass.COMPLIANCE,
            bends=(
                Bend(
                    condition="deadline",
                    instead="ship it anyway",
                    evidence="a Tuesday",
                ),
            ),
        )
    assert "no exception path" in str(caught.value)


def test_a_compliance_rule_cannot_carry_a_scope():
    """A scope reads as a condition, and a compliance rule has none."""
    with pytest.raises(RuleError) as caught:
        Rule(
            id="compliance.authorship",
            text="Authorship is Tee's.",
            rule_class=RuleClass.COMPLIANCE,
            scope=("tqo",),
        )
    assert "reads as a condition" in str(caught.value)


def test_a_craft_rule_with_no_scope_is_refused():
    """Otherwise it ships on every assembly, which is the monolith again."""
    with pytest.raises(RuleError) as caught:
        Rule(
            id="tqo.voice.plain",
            text="Plain words only.",
            rule_class=RuleClass.CRAFT,
        )
    assert "monolith" in str(caught.value)


def test_a_bend_with_no_evidence_is_refused():
    """Rules are never widened on speculation about intent."""
    with pytest.raises(RuleError) as caught:
        Bend(condition="long episode", instead="skip the checklist", evidence="  ")
    assert "speculation" in str(caught.value)


def test_a_bend_that_does_not_say_what_replaces_the_rule_is_refused():
    with pytest.raises(RuleError) as caught:
        Bend(condition="short episode", instead="", evidence="ep 12")
    assert "does not say what the rule becomes" in str(caught.value)


def test_two_bends_on_one_condition_are_refused():
    with pytest.raises(RuleError) as caught:
        Rule(
            id="tqo.pace",
            text="One idea per minute.",
            rule_class=RuleClass.CRAFT,
            scope=("tqo",),
            bends=(
                Bend(condition="deep dive", instead="slow to one per three", evidence="ep 9"),
                Bend(condition="Deep Dive", instead="speed up", evidence="ep 11"),
            ),
        )
    assert "no answer" in str(caught.value)


def test_confidence_outside_the_range_is_refused():
    for bad in (0, -0.1, 1.5):
        with pytest.raises(RuleError):
            Rule(
                id="tqo.x",
                text="x",
                rule_class=RuleClass.CRAFT,
                scope=("tqo",),
                confidence=bad,
            )


def test_a_compliance_rule_never_bends():
    """The load bearing property. Feed it every condition in the ledger."""
    rule = disclosure()
    every_condition = ["correction episode", "deadline", "deep dive", "anything at all"]
    assert rule.bends_under(every_condition) == ()
    assert rule.render(every_condition) == rule.text
    assert rule.applies_to([]) is True
    assert rule.applies_to(["some-unrelated-show"]) is True


def test_a_craft_bend_fires_only_on_its_named_condition():
    rule = hook()
    assert rule.bends_under([]) == ()
    assert rule.bends_under(["deep dive"]) == ()
    fired = rule.bends_under(["Correction Episode"])
    assert len(fired) == 1
    assert "what the earlier episode got wrong" in fired[0].instead
    assert "exception, correction episode:" in rule.render(["correction episode"])


def test_a_craft_rule_is_pulled_only_by_its_scope():
    rule = hook()
    assert rule.applies_to(["tqo"]) is True
    assert rule.applies_to(["TQO"]) is True
    assert rule.applies_to(["tsws"]) is False
    assert rule.applies_to([]) is False


def test_assembly_carries_compliance_always_and_craft_on_request():
    book = ledger()

    narrow = book.assemble(scopes=["tsws"])
    assert set(narrow.ids) == {"compliance.ai-disclosure", "compliance.channel-identity"}

    wide = book.assemble(scopes=["tqo"])
    assert "tqo.hook.learning-objective" in wide.ids
    assert len(wide.compliance) == 2


def test_assembly_order_is_stable_so_two_runs_can_be_diffed():
    book = ledger()
    first = book.assemble(scopes=["tqo"])
    second = book.assemble(scopes=["tqo"])
    assert first.ids == second.ids
    assert first.text() == second.text()
    assert first.ids[0].startswith("compliance.")


def test_an_assembly_missing_a_compliance_rule_is_refused():
    """The real scoping bug, built by hand because the constructor cannot make it.

    This is the failure the teardown names: fragmenting a monolith introduces a
    run that quietly goes out without a rule, and it looks exactly like a run
    that went out with it.
    """
    book = ledger()
    mutilated = Assembly(rules=(disclosure(), hook()), scopes=("tqo",))

    check = check_assembly(mutilated, book, min_chars=0)
    assert check.ok is False
    assert any("compliance.channel-identity" in r for r in check.reasons)
    assert "REFUSED" in check.render()

    with pytest.raises(AssemblyRefused) as caught:
        require_assembly(mutilated, book, min_chars=0)
    assert "compliance.channel-identity" in str(caught.value)


def test_a_thin_assembly_is_refused_against_a_measured_floor():
    book = ledger()
    assembled = book.assemble(scopes=["tqo"])
    body = assembled.text()

    assert check_assembly(assembled, book, min_chars=len(body)).ok is True
    too_thin = check_assembly(assembled, book, min_chars=len(body) + 1)
    assert too_thin.ok is False
    assert "against a floor of" in too_thin.reasons[0]


def test_a_rule_from_outside_the_ledger_is_refused():
    """An assembled prompt drawing on something never reviewed or versioned."""
    book = ledger()
    smuggled = Rule(
        id="from.nowhere",
        text="Say whatever performs.",
        rule_class=RuleClass.CRAFT,
        scope=("tqo",),
    )
    assembly = Assembly(rules=book.assemble(scopes=["tqo"]).rules + (smuggled,), scopes=("tqo",))
    check = check_assembly(assembly, book, min_chars=0)
    assert check.ok is False
    assert any("from.nowhere" in r and "not in the ledger" in r for r in check.reasons)


def test_a_clean_assembly_passes_and_is_handed_straight_back():
    book = ledger()
    assembled = book.assemble(scopes=["tqo"], conditions=["correction episode"])
    assert require_assembly(assembled, book, min_chars=10) is assembled
    assert "ALWAYS ON" in assembled.text()
    assert "exception, correction episode:" in assembled.text()


def test_the_ledger_reports_which_rules_are_still_absolute():
    """Not an error. The count is the thing the teardown says nobody can see."""
    absolute = Rule(
        id="tqo.checklist",
        text="Every episode carries a 3 to 5 step checklist.",
        rule_class=RuleClass.CRAFT,
        scope=("tqo",),
    )
    book = RuleLedger(rules=(disclosure(), hook(), absolute))
    unqualified = book.unqualified()
    assert [r.id for r in unqualified] == ["tqo.checklist"]
    assert absolute.is_unqualified is True
    assert hook().is_unqualified is False
    assert disclosure().is_unqualified is False


def test_two_rules_with_one_id_are_refused():
    with pytest.raises(RuleError) as caught:
        RuleLedger(rules=(hook(), hook()))
    assert "cannot be cited" in str(caught.value)


def test_a_negative_floor_is_refused():
    book = ledger()
    with pytest.raises(RuleError):
        check_assembly(book.assemble(scopes=["tqo"]), book, min_chars=-1)

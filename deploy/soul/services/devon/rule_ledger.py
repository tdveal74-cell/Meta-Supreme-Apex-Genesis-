"""
The exception layer, executable.

Upstream: the AI Impact teardown Tee handed over on 2026-09-17, which read
`github.com/starmynd-org/infinite-brain-os` and the video "How To Build an AI
Infinite Brain" (`xUnVQkPrnrA`, 15 May 2026). One idea in it is worth taking
outright: store the anti patterns beside the best practices as records of the
same standing, because a best practice is right most of the time, and the rest
of the time is exactly the part that has to be written down.

WHY THIS IS CODE AND NOT A DOCUMENT

The teardown's finding about the show canon is the reason. Roughly four
thousand words of TQO positioning, audience tiers, episode architectures and
absolute rules sit inside one n8n node, shipped whole on every episode. That
block carries a long ABSOLUTE RULES section with no exception layer at all.
Every rule in it reads as unconditional, so a model either obeys one stupidly
or breaks it silently, and nothing records which happened.

Writing the exceptions into prose beside the rules does not fix that, for the
reason the rest of this package exists: prose does not enforce. A rule that
knows its own class refuses to carry an exception it may not have, and an
assembly that drops a rule that may never be dropped can be made to fail rather
than to ship quietly.

THE TWO CLASSES, AND WHY THE SPLIT IS THE WHOLE DESIGN

Compliance rules do not bend. Tee's standing rules name the domains: platform
policy, AI disclosure, authorship, rights, channel identity. A compliance rule
carries no exception and no scope, because a scope reads as a condition and a
compliance rule has none. It is present in every assembly by construction.

Craft rules bend, and each one names the conditions under which it does. A
craft rule must declare at least one scope, or it is shipped on every episode
whatever the episode is, which is the monolith again under a new name.

AN EXCEPTION NOBODY HAS SEEN IS A GUESS

Every bend carries evidence. This follows the standing rule against widening a
rule on speculation about intent: an exception invented in advance, against a
case that has not happened, is how a rule gets eroded by the agent that was
supposed to keep it. Write the bend when the case turns up, cite the case.

THE LINE

This module decides which rules an assembly should carry and refuses one that
lost a rule it may not lose. It never decides that a rule should bend. The
conditions are supplied by the caller, and only Tee rules that a new bend
exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

SOURCE = {
    "upstream": "AI Impact teardown and level up blueprint, handed over 2026-09-17",
    "repo_read": "github.com/starmynd-org/infinite-brain-os, MIT",
    "video": "xUnVQkPrnrA, How To Build an AI Infinite Brain, 15 May 2026",
    "read": "2026-09-17",
}

#: The domains Tee's standing rules put outside every exception path. A rule in
#: one of these is compliance class by definition, and the ledger says so rather
#: than leaving it to whoever files the rule.
UNCONDITIONAL_DOMAINS: Tuple[str, ...] = (
    "platform policy",
    "AI disclosure",
    "authorship",
    "rights",
    "channel identity",
)


class RuleClass(str, Enum):
    """Whether a rule bends. The only question the ledger asks of a rule."""

    COMPLIANCE = "compliance"
    CRAFT = "craft"


class RuleError(ValueError):
    """Raised when a rule or an assembly contradicts the doctrine above."""


class AssemblyRefused(RuleError):
    """Raised when an assembly is not safe to send."""


def _normalise(token: str) -> str:
    return " ".join(token.strip().lower().split())


@dataclass(frozen=True)
class Bend:
    """One named condition under which a craft rule does something else.

    `condition` is a token, matched exactly once both sides are normalised, not
    a sentence to be pattern matched. A condition nobody can name in one token
    is a condition nobody can test for.
    """

    condition: str
    instead: str
    evidence: str

    def __post_init__(self) -> None:
        if not self.condition.strip():
            raise RuleError("a bend with no condition cannot be tested for")
        if not self.instead.strip():
            raise RuleError(
                f"bend on '{self.condition}' does not say what the rule becomes. "
                "An exception that only says 'not this' leaves the model to invent "
                "the replacement."
            )
        if not self.evidence.strip():
            raise RuleError(
                f"bend on '{self.condition}' carries no evidence. Cite the episode, "
                "the run, the file and line, or the ruling where this case turned "
                "up. An exception written against a case that has not happened is "
                "speculation, and rules are never widened on speculation."
            )

    @property
    def key(self) -> str:
        return _normalise(self.condition)


@dataclass(frozen=True)
class Rule:
    """One rule, one file's worth of meaning, knowing whether it bends."""

    id: str
    text: str
    rule_class: RuleClass
    scope: Tuple[str, ...] = ()
    confidence: float = 1.0
    bends: Tuple[Bend, ...] = ()
    source: str = ""

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise RuleError("a rule with no id cannot be cited, diffed or retired")
        if not self.text.strip():
            raise RuleError(f"rule '{self.id}' has no text")
        if not isinstance(self.confidence, (int, float)) or isinstance(self.confidence, bool):
            raise RuleError(f"rule '{self.id}' has a non numeric confidence")
        if not 0 < float(self.confidence) <= 1:
            raise RuleError(
                f"rule '{self.id}' has confidence {self.confidence}, outside 0 to 1. "
                "A rule at zero confidence is not a rule, it is a note."
            )
        if self.rule_class is RuleClass.COMPLIANCE:
            if self.bends:
                raise RuleError(
                    f"compliance rule '{self.id}' carries {len(self.bends)} exception(s). "
                    "Compliance covers "
                    + ", ".join(UNCONDITIONAL_DOMAINS)
                    + ", and there is no exception path for any of it. File it as "
                    "craft, or drop the exception."
                )
            if self.scope:
                raise RuleError(
                    f"compliance rule '{self.id}' declares a scope. A scope reads as "
                    "a condition, and a compliance rule has none: it is in every "
                    "assembly by construction."
                )
        else:
            if not self.scope:
                raise RuleError(
                    f"craft rule '{self.id}' declares no scope, so it would ship on "
                    "every assembly whatever the subject is. That is the monolith "
                    "this ledger exists to break up."
                )
            seen: set = set()
            for bend in self.bends:
                if bend.key in seen:
                    raise RuleError(
                        f"craft rule '{self.id}' carries two bends on condition "
                        f"'{bend.condition}'. Two answers to one condition is no answer."
                    )
                seen.add(bend.key)

    @property
    def scope_keys(self) -> Tuple[str, ...]:
        return tuple(_normalise(s) for s in self.scope)

    @property
    def is_unqualified(self) -> bool:
        """A craft rule with no exception written down yet.

        Not an error. Most rules start here, and the teardown's point is that
        the estate should be able to see how many are still absolute purely
        because nobody has hit the exception yet.
        """
        return self.rule_class is RuleClass.CRAFT and not self.bends

    def applies_to(self, scopes: Iterable[str]) -> bool:
        """Compliance applies always. Craft applies when a scope matches."""
        if self.rule_class is RuleClass.COMPLIANCE:
            return True
        wanted = {_normalise(s) for s in scopes}
        return bool(wanted & set(self.scope_keys))

    def bends_under(self, conditions: Iterable[str]) -> Tuple[Bend, ...]:
        """Which exceptions fire, given the conditions the caller observed.

        A compliance rule returns nothing whatever is passed, which is the
        property worth having a test for.
        """
        if self.rule_class is RuleClass.COMPLIANCE:
            return ()
        present = {_normalise(c) for c in conditions}
        return tuple(bend for bend in self.bends if bend.key in present)

    def render(self, conditions: Iterable[str] = ()) -> str:
        """The rule as it should reach the model, with any fired bend attached."""
        lines = [self.text.strip()]
        for bend in self.bends_under(conditions):
            lines.append(f"  exception, {bend.condition}: {bend.instead.strip()}")
        return "\n".join(lines)


@dataclass(frozen=True)
class Assembly:
    """The rule set resolved for one piece of work, and what it was asked for."""

    rules: Tuple[Rule, ...]
    scopes: Tuple[str, ...]
    conditions: Tuple[str, ...] = ()

    @property
    def compliance(self) -> Tuple[Rule, ...]:
        return tuple(r for r in self.rules if r.rule_class is RuleClass.COMPLIANCE)

    @property
    def craft(self) -> Tuple[Rule, ...]:
        return tuple(r for r in self.rules if r.rule_class is RuleClass.CRAFT)

    @property
    def ids(self) -> Tuple[str, ...]:
        return tuple(r.id for r in self.rules)

    def text(self) -> str:
        """What actually gets sent. The thing the guard below measures."""
        blocks: List[str] = []
        if self.compliance:
            blocks.append("ALWAYS ON")
            blocks.extend(r.render(self.conditions) for r in self.compliance)
        if self.craft:
            blocks.append("FOR THIS ONE")
            blocks.extend(r.render(self.conditions) for r in self.craft)
        return "\n\n".join(blocks)


@dataclass(frozen=True)
class AssemblyCheck:
    """The verdict on one assembly, naming every reason it is not safe."""

    ok: bool
    reasons: Tuple[str, ...] = ()

    def render(self) -> str:
        if self.ok:
            return "assembly OK"
        return "assembly REFUSED\n" + "\n".join(f"  {r}" for r in self.reasons)


@dataclass
class RuleLedger:
    """Every rule that exists, and the only place an assembly may draw from."""

    rules: Tuple[Rule, ...] = ()

    def __post_init__(self) -> None:
        self.rules = tuple(self.rules)
        seen: Dict[str, Rule] = {}
        for rule in self.rules:
            if rule.id in seen:
                raise RuleError(
                    f"two rules carry the id '{rule.id}'. An id that resolves to two "
                    "rules cannot be cited in a review or retired in one edit."
                )
            seen[rule.id] = rule

    def by_id(self, rule_id: str) -> Optional[Rule]:
        for rule in self.rules:
            if rule.id == rule_id:
                return rule
        return None

    @property
    def compliance(self) -> Tuple[Rule, ...]:
        return tuple(r for r in self.rules if r.rule_class is RuleClass.COMPLIANCE)

    @property
    def craft(self) -> Tuple[Rule, ...]:
        return tuple(r for r in self.rules if r.rule_class is RuleClass.CRAFT)

    def unqualified(self) -> Tuple[Rule, ...]:
        """Craft rules that still read as absolute because no case has landed."""
        return tuple(r for r in self.rules if r.is_unqualified)

    def scopes(self) -> Tuple[str, ...]:
        found: set = set()
        for rule in self.craft:
            found.update(rule.scope_keys)
        return tuple(sorted(found))

    def assemble(
        self,
        scopes: Sequence[str] = (),
        conditions: Sequence[str] = (),
    ) -> Assembly:
        """Every compliance rule, plus the craft rules this subject asked for.

        Order is compliance first, then craft in ledger order, so two assemblies
        for the same scope render byte identical and can be diffed.
        """
        wanted = tuple(scopes)
        chosen = tuple(r for r in self.rules if r.applies_to(wanted))
        ordered = tuple(
            sorted(chosen, key=lambda r: 0 if r.rule_class is RuleClass.COMPLIANCE else 1)
        )
        return Assembly(rules=ordered, scopes=wanted, conditions=tuple(conditions))


def check_assembly(assembly: Assembly, ledger: RuleLedger, min_chars: int) -> AssemblyCheck:
    """Refuse an assembly that lost a rule it may not lose, or came out thin.

    This is the guard the teardown asks for before a scoped prompt goes out. The
    failure mode that scoping introduces is an assembled prompt that quietly
    drops a rule, and the run that produces a script without it looks exactly
    like a run that produced one with it.

    `min_chars` has no default on purpose. A floor nobody measured is a guess,
    and the whole point of this check is to stop guesses reaching the model.
    Measure the monolith the fragments replaced and pass that.
    """
    if min_chars < 0:
        raise RuleError("min_chars cannot be negative")

    reasons: List[str] = []

    known = {rule.id for rule in ledger.rules}
    strangers = [rule.id for rule in assembly.rules if rule.id not in known]
    for stranger in strangers:
        reasons.append(
            f"rule '{stranger}' is in the assembly and not in the ledger, so it was "
            "never reviewed, versioned or tested"
        )

    present = set(assembly.ids)
    for rule in ledger.compliance:
        if rule.id not in present:
            reasons.append(
                f"compliance rule '{rule.id}' is missing from the assembly. "
                "Compliance is always on and this run would go out without it"
            )

    body = assembly.text()
    if len(body) < min_chars:
        reasons.append(
            f"assembled text is {len(body)} characters against a floor of {min_chars}, "
            "which is the shape of an assembly that resolved to almost nothing"
        )

    return AssemblyCheck(ok=not reasons, reasons=tuple(reasons))


def require_assembly(assembly: Assembly, ledger: RuleLedger, min_chars: int) -> Assembly:
    """The refusing form. Use this on the path that actually sends the prompt."""
    check = check_assembly(assembly, ledger, min_chars)
    if not check.ok:
        raise AssemblyRefused(check.render())
    return assembly

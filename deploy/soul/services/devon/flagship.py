"""
The Flagship Bar, executable.

Source on Drive: SYS_SPEC_flagship-bar_v01_2026-08-21
(Drive id 1s4l6r9ucGWrtEENqlBqDmFtpl4_85z_m), read 2026-08-22.

The ship minimum for any deliverable produced under AAA FLAGSHIP META SUPREME.
Written down on 2026-08-21 because a standard living only in conversation is not
a standard, it is a habit.

Run the gauntlet before presenting a code change, an automation or config edit, a
data mutation, content, or a plan that will be acted on. Skip it for
conversational answers and trivial one liners. The bar is for work that will be
trusted, merged, run, published or shipped.

INSPECT, THEN HAND BACK. This module produces a verdict with receipts. The human
owns SHIP. Nothing here marks anything shipped, approved or merged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Tuple

SOURCE = {
    "drive_id": "1s4l6r9ucGWrtEENqlBqDmFtpl4_85z_m",
    "title": "SYS_SPEC_flagship-bar_v01_2026-08-21",
    "read": "2026-08-22",
}


@dataclass(frozen=True)
class Clause:
    number: int
    title: str
    test: str


CLAUSES: Tuple[Clause, ...] = (
    Clause(
        1,
        "Root, not symptom",
        "It fixes the actual cause. A watchdog that reports clean because the field "
        "name is wrong has fixed nothing. Ask what would still be broken if this shipped.",
    ),
    Clause(
        2,
        "Simplest form that fully works",
        "Not the cleverest, not the most complete. The smallest thing that does the "
        "job end to end. Extra surface is extra failure.",
    ),
    Clause(
        3,
        "Handed off clean",
        "Verified, reversible where it matters, one clear next step, in house "
        "conventions and voice. The receiving human should not have to reconstruct intent.",
    ),
)

DIMENSIONS: Tuple[str, ...] = (
    "scope fidelity",
    "correctness",
    "unverified claims",
    "security",
    "reversibility and blast radius",
    "silent failure resistance",
    "idempotency",
    "traceability",
    "observability",
    "completeness",
    "maintainability",
    "flagship bar",
)

MIN_PER_DIMENSION = 3
MIN_MEAN = 4.0
REQUIRED_SECURITY = 5
MIN_VERIFICATION = 4
MAX_REVISION_CYCLES = 3


class Verdict(str, Enum):
    PASS = "PASS"
    PASS_WITH_CONDITIONS = "PASS-WITH-CONDITIONS"
    QUARANTINE = "QUARANTINE"


class CriticMode(str, Enum):
    FRESH = "fresh"
    SIMULATED = "simulated"


class ScoringError(ValueError):
    """Raised when a score set cannot be evaluated."""


@dataclass
class Finding:
    """One defect, carrying its evidence. Without evidence it does not exist."""

    location: str
    problem: str
    consequence: str
    owner: str
    evidence: str = ""

    def __post_init__(self) -> None:
        if not self.evidence:
            raise ScoringError(
                f"Finding at {self.location} has no evidence. Findings carry "
                "file:line, node and param, execution id, exact value, or failing "
                "input. Without one, the finding does not exist."
            )

    def render(self) -> str:
        return (
            f"  {self.location} - {self.problem} - {self.consequence} "
            f"- owner: {self.owner}\n    evidence: {self.evidence}"
        )


@dataclass
class Assessment:
    """A scored deliverable and the verdict that follows from the scores."""

    subject: str
    scores: Dict[str, int]
    clauses_met: Dict[int, bool]
    verification_score: int
    critic_mode: CriticMode
    findings: List[Finding] = field(default_factory=list)
    receipts: List[str] = field(default_factory=list)
    recommendation: str = ""
    revision_cycle: int = 0

    def __post_init__(self) -> None:
        unknown = set(self.scores) - set(DIMENSIONS)
        if unknown:
            raise ScoringError(f"Unknown dimensions: {', '.join(sorted(unknown))}")
        missing = set(DIMENSIONS) - set(self.scores)
        if missing:
            raise ScoringError(
                "Every dimension must be scored. Missing: "
                + ", ".join(sorted(missing))
                + ". An unscored dimension is an unexamined one."
            )
        for name, value in self.scores.items():
            if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 5:
                raise ScoringError(f"Score for '{name}' must be an integer 1 to 5, got {value!r}")

    @property
    def mean(self) -> float:
        return sum(self.scores.values()) / len(self.scores)

    @property
    def bar_met(self) -> bool:
        """All three clauses, or the bar is not met."""
        return all(self.clauses_met.get(c.number, False) for c in CLAUSES)

    def failures(self) -> List[str]:
        """Every reason this is not a PASS, named explicitly."""
        reasons: List[str] = []
        for name, value in sorted(self.scores.items()):
            if value < MIN_PER_DIMENSION:
                reasons.append(f"{name} scored {value}, below the floor of {MIN_PER_DIMENSION}")
        if self.mean < MIN_MEAN:
            reasons.append(f"mean {self.mean:.2f} is below {MIN_MEAN}")
        if self.scores.get("security") != REQUIRED_SECURITY:
            reasons.append(
                f"security scored {self.scores.get('security')}, and PASS requires "
                f"exactly {REQUIRED_SECURITY}"
            )
        if self.verification_score < MIN_VERIFICATION:
            reasons.append(
                f"verification scored {self.verification_score}, below {MIN_VERIFICATION}"
            )
        if not self.bar_met:
            unmet = [c for c in CLAUSES if not self.clauses_met.get(c.number, False)]
            for clause in unmet:
                reasons.append(f"clause {clause.number} ({clause.title}) not met")
        return reasons

    @property
    def verdict(self) -> Verdict:
        """PASS requires every condition. Anything short is conditional or quarantined.

        A deliverable that has already burned its revision cycles is quarantined
        rather than passed with conditions, because the third failed revision is
        evidence the approach is wrong, not that the notes were unclear.
        """
        reasons = self.failures()
        if not reasons:
            return Verdict.PASS
        if self.revision_cycle >= MAX_REVISION_CYCLES:
            return Verdict.QUARANTINE
        blocking = [
            r
            for r in reasons
            if r.startswith("security") or "below the floor" in r or "not met" in r
        ]
        return Verdict.QUARANTINE if blocking else Verdict.PASS_WITH_CONDITIONS

    @property
    def needs_human_review(self) -> bool:
        """A ship affecting PASS from a simulated critic still needs a human."""
        return self.critic_mode is CriticMode.SIMULATED and self.verdict is Verdict.PASS

    def render(self) -> str:
        """The verdict format emitted with every ship worthy deliverable."""
        lines = [
            f"VERDICT: {self.verdict.value}",
            f"Subject: {self.subject}",
            f"critic_mode: {self.critic_mode.value}",
            "Scores:",
        ]
        for name in DIMENSIONS:
            lines.append(f"  {name}: {self.scores[name]}")
        lines.append(f"  verification: {self.verification_score}")
        lines.append(f"  mean: {self.mean:.2f}")
        lines.append(
            "  flagship bar: " + ("met" if self.bar_met else "MISSED")
        )
        for clause in CLAUSES:
            state = "met" if self.clauses_met.get(clause.number, False) else "MISSED"
            lines.append(f"    clause {clause.number} {clause.title}: {state}")

        reasons = self.failures()
        if reasons:
            lines.append("Blocking:")
            for reason in reasons:
                lines.append(f"  {reason}")

        lines.append("Findings:")
        if self.findings:
            for finding in self.findings:
                lines.append(finding.render())
        else:
            lines.append("  none")

        lines.append("Receipts:")
        if self.receipts:
            for receipt in self.receipts:
                lines.append(f"  {receipt}")
        else:
            lines.append(
                "  none. A verdict with no receipts is an assertion, and assertion "
                "is not result."
            )

        lines.append(f"Recommendation: {self.recommendation or 'none stated'}")

        if self.needs_human_review:
            lines.append(
                "NOTE: no fresh critic reviewed this cold. Treat this ship affecting "
                "PASS as needing human review."
            )
        lines.append("INSPECT, THEN HAND BACK. The human owns SHIP.")
        return "\n".join(lines)


# The seven logged instances of the standing failure class, kept so that a
# reviewer checking a deliverable has the shapes in front of them.
STALE_ARTIFACT_INSTANCES: Tuple[str, ...] = (
    "Context Pill: two byte identical v12 files, one marked REGRESSION, one not",
    "NYREN against Vespera: thread open 21 days after the ruling closed it",
    "FKR gauntlet docs claiming no code over a working implementation",
    "update_workflow reporting a patch applied that never persisted",
    "Two executions returning success while doing nothing useful",
    "An expired Gmail credential failing silently for an unknown period",
    "A rejected architecture board propagating into a later spec document",
)

STALE_ARTIFACT_SHAPE = "Something claims a state it has not got."
STALE_ARTIFACT_DEFENSE = "Not more artifacts. Write-back and read-back."


def requires_gauntlet(deliverable_kind: str) -> bool:
    """Whether a deliverable must run the gauntlet before being presented."""
    ship_worthy = {
        "code",
        "diff",
        "automation",
        "workflow",
        "config",
        "migration",
        "data mutation",
        "content",
        "plan",
    }
    kind = (deliverable_kind or "").strip().lower()
    return any(token in kind for token in ship_worthy)


def blank_scores(default: int = 3) -> Dict[str, int]:
    """A scoring sheet with every dimension present, for a reviewer to fill in."""
    return {name: default for name in DIMENSIONS}

"""The lessons loop: a check written after a loss that can only block a trade.

Source lines 63 and 88-89 (DOC): a lost trade leaves a lesson, and a lesson
may only make the desk refuse more, never less. A weekly review may change at
most three settings and only with a named person's approval.

INVENTED, SPEC.md: the rule that derives a lesson from a losing position
(``derive_lesson``) and the check grammar are written for this build and wait
on the owner's review.

Pure code. A check is parsed by a regular expression and compared with the
operator module's functions; nothing is ever evaluated as code. No clock, no
network, no mutation of arguments.
"""
from __future__ import annotations

import operator
import re
from dataclasses import asdict, dataclass, fields
from typing import Any, Callable

from .model import Fill, HumanApproval, Lesson, Position, TokenSnapshot
from .positions import realized_pnl
from .settings import Settings

CHECK_FIELDS = (
    "liquidity_usd",
    "change_1h_pct",
    "top10_pct",
    "dev_pct",
    "lp_locked_or_burned_pct",
    "bundled_wallets",
    "insiders_pct",
    "holders",
    "buys_5m",
    "sells_5m",
    "pool_age_s",
)

_OPS: dict[str, Callable[[float, float], bool]] = {
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
}

_NUMBER = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")

MAX_REVIEW_CHANGES = 3


class LessonError(ValueError):
    """A check, a lesson row or a review is not acceptable."""


@dataclass(frozen=True)
class Check:
    """``<field> <op> <number>``. True on a snapshot means: refuse this coin."""

    field: str
    op: str
    value: float


def parse_check(text: str) -> Check:
    """Parse ``<field> <op> <number>``. Raises LessonError on anything else."""
    if not isinstance(text, str):
        raise LessonError("a check must be text")
    parts = text.split()
    if len(parts) != 3:
        raise LessonError(f"a check is '<field> <op> <number>', got {text!r}")
    field, op, number = parts
    if field not in CHECK_FIELDS:
        raise LessonError(f"unknown check field {field!r}")
    if op not in _OPS:
        raise LessonError(f"unknown check operator {op!r}")
    if _NUMBER.fullmatch(number) is None:
        raise LessonError(f"not a number: {number!r}")
    value = float(number)
    if value != value or value in (float("inf"), float("-inf")):
        raise LessonError(f"not a finite number: {number!r}")
    return Check(field, op, value)


def _field_value(check: Check, snap: TokenSnapshot) -> float | None:
    if check.field == "pool_age_s":
        if snap.pool_created_ts is None:
            return None
        return float(snap.ts - snap.pool_created_ts)
    if check.field not in CHECK_FIELDS:
        raise LessonError(f"unknown check field {check.field!r}")
    value = getattr(snap, check.field)
    return None if value is None else float(value)


def check_hits(check: Check, snap: TokenSnapshot) -> bool:
    """True when the condition holds, or when the field is unknown."""
    if check.op not in _OPS:
        raise LessonError(f"unknown check operator {check.op!r}")
    value = _field_value(check, snap)
    if value is None:
        return True
    return bool(_OPS[check.op](value, check.value))


def derive_lesson(position: Position, exit_fill: Fill, settings: Settings) -> Lesson | None:
    """The lesson a losing position leaves, or None when none qualifies.

    INVENTED rule. A position that did not lose money leaves no lesson. For a
    loss, the entry snapshot's field that sat closest to its limit is turned
    into a check that refuses the next coin at or past that value.
    """
    if realized_pnl(position, exit_fill) >= 0:
        return None
    snap = position.entry_snapshot
    # (field, value, limit, higher_is_worse), in the order SPEC.md lists them.
    candidates = (
        ("top10_pct", snap.top10_pct, settings.top10_max_pct, True),
        ("dev_pct", snap.dev_pct, settings.dev_max_pct, True),
        ("insiders_pct", snap.insiders_pct, settings.insiders_max_pct, True),
        ("bundled_wallets", snap.bundled_wallets, settings.bundled_wallets_max, True),
        ("liquidity_usd", snap.liquidity_usd, settings.liquidity_floor_usd, False),
    )
    best: tuple[float, str, float, bool] | None = None
    for name, value, limit, higher_is_worse in candidates:
        if value is None or limit is None or value <= 0 or limit <= 0:
            continue
        closeness = value / limit if higher_is_worse else limit / value
        if best is None or closeness > best[0]:
            best = (closeness, name, float(value), higher_is_worse)
    if best is None:
        return None
    _, name, value, higher_is_worse = best
    op = ">=" if higher_is_worse else "<="
    return Lesson(
        lesson_id=f"L-{position.mint}-{exit_fill.ts}",
        created_ts=exit_fill.ts,
        source_mint=position.mint,
        check=f"{name} {op} {value!r}",
        why=f"{position.symbol} lost money and entered with {name} {value!r}, the field closest to its limit",
    )


def apply_review(settings: Settings, changes: dict, approval: HumanApproval | None) -> Settings:
    """Settings after a human approved review (source line 89).

    Raises LessonError without an approval or with more than three changes.
    The result goes through ``Settings.from_dict``, so names and ranges are
    checked. The arguments are not changed.
    """
    if approval is None:
        raise LessonError("a review needs a named person's approval")
    if len(changes) > MAX_REVIEW_CHANGES:
        raise LessonError(f"a review may change at most {MAX_REVIEW_CHANGES} settings, got {len(changes)}")
    merged: dict[str, Any] = asdict(settings)
    merged.update(changes)
    return Settings.from_dict(merged)


_LESSON_KEYS = frozenset(f.name for f in fields(Lesson))


class LessonBook:
    """Lessons in the order they were added. Nothing here removes or weakens one."""

    def __init__(self) -> None:
        self._lessons: list[Lesson] = []
        self._parsed: list[Check] = []

    def add(self, lesson: Lesson) -> Lesson:
        """Store a lesson, or return the existing one with the same check text."""
        check = parse_check(lesson.check)
        for existing in self._lessons:
            if existing.check == lesson.check:
                return existing
        self._lessons.append(lesson)
        self._parsed.append(check)
        return lesson

    def blocking(self, snap: TokenSnapshot) -> Lesson | None:
        """The first lesson, in the order added, whose check hits this coin."""
        for lesson, check in zip(self._lessons, self._parsed, strict=True):
            if check_hits(check, snap):
                return lesson
        return None

    def to_json(self) -> list[dict]:
        return [asdict(lesson) for lesson in self._lessons]

    @classmethod
    def from_json(cls, rows: list[dict]) -> LessonBook:
        book = cls()
        for row in rows:
            if not isinstance(row, dict) or set(row) - _LESSON_KEYS or not {
                "lesson_id", "created_ts", "source_mint", "check"
            } <= set(row):
                raise LessonError("a lesson row has missing or unknown keys")
            book.add(Lesson(**row))
        return book

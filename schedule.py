"""
Schedule cadences — parsing and next-slot arithmetic.

Framework-free and pure: no database, no clock of its own (every function
takes `now` explicitly), so the dispatcher's behaviour is fully testable
without freezing time globally.

Three cadence forms, all UTC:

    hourly:MM              every hour at MM past
    daily:HH:MM            every day at HH:MM
    weekly:DOW:HH:MM       every DOW at HH:MM  (mon tue wed thu fri sat sun)

Deliberately not cron. Cron's expressiveness (ranges, steps, day-of-month
with its month-length edge cases) is a large surface to get right, and no
product requirement has asked for it. When one does, replace this module —
its interface is two functions.

**Cadences already stored may not parse.** Definition validation before 5.1
required only a non-empty `cadence` string, so a workflow can hold anything.
`parse_cadence` raises `CadenceError` and the dispatcher treats that as a
skip-with-reason, never as a crash: one malformed workflow must not stop the
batch for every other tenant.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

__all__ = ["Cadence", "CadenceError", "parse_cadence", "next_slot", "describe_cadence"]

_DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

_HOURLY_RE = re.compile(r"^hourly:(\d{1,2})$")
_DAILY_RE = re.compile(r"^daily:(\d{1,2}):(\d{1,2})$")
_WEEKLY_RE = re.compile(r"^weekly:([a-z]{3}):(\d{1,2}):(\d{1,2})$")


class CadenceError(ValueError):
    """The cadence string is not one this dispatcher understands."""


@dataclass(frozen=True)
class Cadence:
    kind: str  # "hourly" | "daily" | "weekly"
    minute: int
    hour: Optional[int] = None
    weekday: Optional[int] = None  # 0 = Monday, matching datetime.weekday()


def parse_cadence(raw: object) -> Cadence:
    text = str(raw or "").strip().lower()
    if not text:
        raise CadenceError("Cadence is empty")

    if m := _HOURLY_RE.match(text):
        minute = int(m.group(1))
        _check(minute <= 59, f"Minute {minute} is out of range in {text!r}")
        return Cadence(kind="hourly", minute=minute)

    if m := _DAILY_RE.match(text):
        hour, minute = int(m.group(1)), int(m.group(2))
        _check(hour <= 23 and minute <= 59, f"Time out of range in {text!r}")
        return Cadence(kind="daily", hour=hour, minute=minute)

    if m := _WEEKLY_RE.match(text):
        day, hour, minute = m.group(1), int(m.group(2)), int(m.group(3))
        _check(day in _DAYS, f"Unknown day {day!r} in {text!r}")
        _check(hour <= 23 and minute <= 59, f"Time out of range in {text!r}")
        return Cadence(
            kind="weekly", weekday=_DAYS.index(day), hour=hour, minute=minute
        )

    raise CadenceError(
        f"Cadence {text!r} is not understood. Expected hourly:MM, "
        f"daily:HH:MM, or weekly:DOW:HH:MM (UTC)."
    )


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise CadenceError(message)


def next_slot(cadence: Cadence, after: datetime) -> datetime:
    """
    The first firing strictly after `after`.

    Strictly after, never equal: called with a workflow's own `last_fired_at`,
    an inclusive boundary would return the slot that just fired and the
    workflow would fire twice for one slot.
    """
    if after.tzinfo is None:
        raise ValueError("`after` must be timezone-aware")
    after = after.astimezone(timezone.utc)

    if cadence.kind == "hourly":
        candidate = after.replace(minute=cadence.minute, second=0, microsecond=0)
        while candidate <= after:
            candidate += timedelta(hours=1)
        return candidate

    if cadence.kind == "daily":
        candidate = after.replace(
            hour=cadence.hour, minute=cadence.minute, second=0, microsecond=0
        )
        while candidate <= after:
            candidate += timedelta(days=1)
        return candidate

    if cadence.kind == "weekly":
        candidate = after.replace(
            hour=cadence.hour, minute=cadence.minute, second=0, microsecond=0
        )
        days_ahead = (cadence.weekday - candidate.weekday()) % 7
        candidate += timedelta(days=days_ahead)
        while candidate <= after:
            candidate += timedelta(days=7)
        return candidate

    raise CadenceError(f"Unknown cadence kind {cadence.kind!r}")


def describe_cadence(cadence: Cadence) -> str:
    """Human-readable, for the UI and for dispatcher logs."""
    time = f"{cadence.hour:02d}:{cadence.minute:02d}" if cadence.hour is not None else ""
    if cadence.kind == "hourly":
        return f"every hour at :{cadence.minute:02d} UTC"
    if cadence.kind == "daily":
        return f"every day at {time} UTC"
    return f"every {_DAYS[cadence.weekday].capitalize()} at {time} UTC"

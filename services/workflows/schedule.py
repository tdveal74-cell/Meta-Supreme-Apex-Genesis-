"""Schedule trigger helpers for workflow dispatch (Phase 5.1)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional


def parse_cadence(cadence: str) -> Optional[str]:
    """Return normalized cadence or None if unparseable.

    Supported:
      hourly:MM
      daily:HH:MM
      weekly:DOW:HH:MM   (DOW 0=Monday … 6=Sunday, UTC)
    """
    raw = (cadence or "").strip().lower()
    if not raw:
        return None
    parts = raw.split(":")
    if parts[0] == "hourly" and len(parts) == 2:
        try:
            minute = int(parts[1])
        except ValueError:
            return None
        if 0 <= minute <= 59:
            return f"hourly:{minute:02d}"
        return None
    if parts[0] == "daily" and len(parts) == 3:
        try:
            hour, minute = int(parts[1]), int(parts[2])
        except ValueError:
            return None
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"daily:{hour:02d}:{minute:02d}"
        return None
    if parts[0] == "weekly" and len(parts) == 4:
        try:
            dow, hour, minute = int(parts[1]), int(parts[2]), int(parts[3])
        except ValueError:
            return None
        if 0 <= dow <= 6 and 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"weekly:{dow}:{hour:02d}:{minute:02d}"
        return None
    return None


def next_run_after(cadence: str, *, after: Optional[datetime] = None) -> Optional[datetime]:
    """Compute the next UTC fire time strictly after `after` (default now)."""
    normalized = parse_cadence(cadence)
    if not normalized:
        return None
    after = after or datetime.now(timezone.utc)
    if after.tzinfo is None:
        after = after.replace(tzinfo=timezone.utc)

    parts = normalized.split(":")
    kind = parts[0]

    if kind == "hourly":
        minute = int(parts[1])
        candidate = after.replace(minute=minute, second=0, microsecond=0)
        if candidate <= after:
            candidate += timedelta(hours=1)
        return candidate

    if kind == "daily":
        hour, minute = int(parts[1]), int(parts[2])
        candidate = after.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= after:
            candidate += timedelta(days=1)
        return candidate

    if kind == "weekly":
        dow, hour, minute = int(parts[1]), int(parts[2]), int(parts[3])
        candidate = after.replace(hour=hour, minute=minute, second=0, microsecond=0)
        days_ahead = (dow - candidate.weekday()) % 7
        candidate += timedelta(days=days_ahead)
        if candidate <= after:
            candidate += timedelta(days=7)
        return candidate

    return None

"""Pure missed-run policy for the durable, one-shot goal scheduler."""

from datetime import datetime, timezone
from typing import Any

POLICY_KEY = "_schedule_policy"


def schedule_context(context: dict[str, Any] | None, run_at: datetime) -> dict[str, Any]:
    """Validate policy and bind expiry to the original slot, not retry backoff."""
    result = dict(context or {})
    raw = result.get(POLICY_KEY, {})
    if not isinstance(raw, dict):
        raise ValueError("schedule policy must be an object")
    policy = raw.get("missed_run_policy", "catch_up")
    lateness = raw.get("max_lateness_seconds", 300)
    if policy not in ("catch_up", "skip"):
        raise ValueError("missed_run_policy must be catch_up or skip")
    if type(lateness) is not int or not 0 <= lateness <= 31_536_000:
        raise ValueError("max_lateness_seconds must be an integer from 0 to 31536000")
    result[POLICY_KEY] = {
        "missed_run_policy": policy,
        "max_lateness_seconds": lateness,
        "original_run_at": run_at.isoformat(),
    }
    return result


def missed_run_expired(context: dict[str, Any], run_at: datetime, now: datetime) -> bool:
    raw = context.get(POLICY_KEY, {})
    # Validate again when reading persisted data; malformed policy never runs.
    validated = schedule_context(context, run_at)[POLICY_KEY]
    if validated["missed_run_policy"] == "catch_up":
        return False
    original = raw.get("original_run_at")
    slot = datetime.fromisoformat(original) if original is not None else run_at
    if slot.tzinfo is None:
        slot = slot.replace(tzinfo=timezone.utc)
    return (now - slot).total_seconds() > validated["max_lateness_seconds"]

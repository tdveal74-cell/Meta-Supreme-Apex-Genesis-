"""Health evidence summary. Missing evidence cannot become a passing check."""

from datetime import datetime, timezone

from tools.devon_rsi.kernel import Refused, digest


def summarize(evidence, now=None):
    now = now or datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None or not isinstance(evidence, dict) or set(evidence) != {
        "reflection_count", "latest_reflection_at", "canon_count_previous", "canon_count_current",
        "disagreements", "blind_test_distinguishable", "monthly_review_at", "source_sha256"
    }:
        raise Refused("HEALTH_SCHEMA")
    from .store import safe_hash
    safe_hash(evidence["source_sha256"])
    for key in ("reflection_count", "canon_count_previous", "canon_count_current", "disagreements"):
        if evidence[key] is not None and (type(evidence[key]) is not int or evidence[key] < 0):
            raise Refused("HEALTH_COUNT")
    if type(evidence["blind_test_distinguishable"]) not in {bool, type(None)}:
        raise Refused("HEALTH_BLIND_TEST")
    times = {}
    for key in ("latest_reflection_at", "monthly_review_at"):
        value = evidence[key]
        if value is not None and (type(value) is not str or not value):
            raise Refused("HEALTH_TIME")
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00")) if value is not None else None
        except ValueError:
            raise Refused("HEALTH_TIME") from None
        if parsed and (parsed.tzinfo is None or parsed > now):
            raise Refused("HEALTH_TIME")
        times[key] = parsed
    previous, current = evidence["canon_count_previous"], evidence["canon_count_current"]
    monthly = times["monthly_review_at"]
    reflection = times["latest_reflection_at"]
    return {"status": "REVIEW_REQUIRED", "evidence_sha256": digest(evidence),
            "reflection_count": evidence["reflection_count"],
            "reflection_age_hours": round((now - reflection).total_seconds() / 3600, 2) if reflection else None,
            "canon_growth": current - previous if current is not None and previous is not None else None,
            "disagreements": evidence["disagreements"],
            "blind_test_distinguishable": evidence["blind_test_distinguishable"],
            "monthly_review_recorded": bool(monthly and (monthly.year, monthly.month) == (now.year, now.month)),
            "unknown_metrics": [k for k, v in evidence.items() if v is None],
            "human_health_judgment_required": True, "gain_claim": False, "promoted": False}

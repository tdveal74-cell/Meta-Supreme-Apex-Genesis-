"""BOT 2, the analyst: an eight layer safety audit, then a score for survivors.

The audit comes from source lines 45-53 of the prompt. Evaluation stops at the
first layer that is not green, and an unknown is never green.

The score comes from source line 54, which names five parts and defines none.
INVENTED (formula v0, SPEC.md): every formula for ``alive``, ``organic``,
``flush``, ``anti_chase`` and ``social``, and the settings they read
(``score_alive_trades_full``, ``score_antichase_full_below_pct``,
``score_flush_full_min_pct``, ``score_flush_full_max_pct``,
``social_max_bonus``). The pass and full thresholds are from source lines 54
and 57. Social can only raise the score.

Pure functions. No clock: the time is always ``snap.ts``.
"""
from __future__ import annotations

from .model import AuditResult, LayerResult, LayerStatus, ScoreBreakdown, TokenSnapshot
from .settings import Settings

_GREEN = LayerStatus.GREEN
_RED = LayerStatus.RED
_UNKNOWN = LayerStatus.UNKNOWN


def _flag(value: bool | None, detail: str) -> tuple[LayerStatus, str]:
    """Green when True, red when False, unknown when None."""
    if value is None:
        return _UNKNOWN, f"{detail} unknown"
    return (_GREEN if value else _RED), detail


def _layers(snap: TokenSnapshot, s: Settings):
    """Yield (number, name, evaluator) in order. Evaluators are lazy."""

    def l1() -> tuple[LayerStatus, str]:
        return _flag(snap.mint_authority_revoked, "mint authority revoked")

    def l2() -> tuple[LayerStatus, str]:
        return _flag(snap.freeze_authority_revoked, "freeze authority revoked")

    def l3() -> tuple[LayerStatus, str]:
        dev, sold = snap.dev_pct, snap.dev_has_sold
        if (dev is not None and dev >= s.dev_max_pct) or sold is True:
            return _RED, f"dev_pct {dev} limit {s.dev_max_pct}, dev_has_sold {sold}"
        if dev is None or sold is None:
            return _UNKNOWN, f"dev_pct {dev}, dev_has_sold {sold}"
        return _GREEN, f"dev_pct {dev} < {s.dev_max_pct}, has not sold"

    def l4() -> tuple[LayerStatus, str]:
        v = snap.top10_pct
        if v is None:
            return _UNKNOWN, "top10_pct unknown"
        return (_GREEN if v < s.top10_max_pct else _RED), f"top10_pct {v} limit {s.top10_max_pct}"

    def l5() -> tuple[LayerStatus, str]:
        v = snap.lp_locked_or_burned_pct
        if v is None:
            return _UNKNOWN, "lp_locked_or_burned_pct unknown"
        return (_GREEN if v >= s.lp_locked_min_pct else _RED), f"lp locked {v} minimum {s.lp_locked_min_pct}"

    def l6() -> tuple[LayerStatus, str]:
        if snap.pool_created_ts is None:
            return _UNKNOWN, "pool_created_ts unknown"
        age = snap.ts - snap.pool_created_ts
        return (_GREEN if age >= s.pool_age_min_s else _RED), f"pool age {age}s minimum {s.pool_age_min_s}s"

    def l7() -> tuple[LayerStatus, str]:
        b, i = snap.bundled_wallets, snap.insiders_pct
        if (b is not None and b >= s.bundled_wallets_max) or (i is not None and i >= s.insiders_max_pct):
            return _RED, f"bundled_wallets {b} limit {s.bundled_wallets_max}, insiders_pct {i} limit {s.insiders_max_pct}"
        if b is None or i is None:
            return _UNKNOWN, f"bundled_wallets {b}, insiders_pct {i}"
        return _GREEN, f"bundled_wallets {b}, insiders_pct {i}"

    def l8() -> tuple[LayerStatus, str]:
        v = snap.dangerous_delegation
        if v is None:
            return _UNKNOWN, "dangerous_delegation unknown"
        return (_RED if v else _GREEN), f"dangerous_delegation {v}"

    return (
        (1, "mint authority revoked", l1),
        (2, "freeze authority revoked", l2),
        (3, "dev holds under limit and has not sold", l3),
        (4, "top 10 under limit", l4),
        (5, "LP locked or burned", l5),
        (6, "pool age", l6),
        (7, "bundles and insiders", l7),
        (8, "no dangerous delegations", l8),
    )


def audit(snap: TokenSnapshot, settings: Settings) -> AuditResult:
    """Run the eight layers in order and stop at the first that is not green."""
    done: list[LayerResult] = []
    for number, name, evaluate in _layers(snap, settings):
        status, detail = evaluate()
        layer = LayerResult(number, name, status, detail)
        done.append(layer)
        if status is not _GREEN:
            return AuditResult(tuple(done), False, layer)
    return AuditResult(tuple(done), True, None)


def _flush(snap: TokenSnapshot, s: Settings) -> float:
    high, price = snap.high_10m_usd, snap.price_usd
    if high is None or price is None or high <= 0:
        return 0.0
    p = (high - price) / high * 100
    lo, hi = s.score_flush_full_min_pct, s.score_flush_full_max_pct
    if p <= 0:
        return 0.0
    if p < lo:
        return 25.0 * p / lo
    if p <= hi:
        return 25.0
    width = hi - lo
    if p < hi + width:
        return 25.0 * (1 - (p - hi) / width)
    return 0.0


def _anti_chase(snap: TokenSnapshot, s: Settings) -> float:
    g = snap.change_1h_pct
    if g is None:
        return 0.0
    full_below, kill = s.score_antichase_full_below_pct, s.pump_1h_kill_pct
    if g <= full_below:
        return 25.0
    if g >= kill:
        return 0.0
    return 25.0 * (kill - g) / (kill - full_below)


def score(snap: TokenSnapshot, settings: Settings) -> ScoreBreakdown:
    """The v0 score (INVENTED formula). Any missing input zeroes its part."""
    s = settings
    if snap.buys_5m is None or snap.sells_5m is None:
        alive = 0.0
    else:
        alive = 25.0 * min(1.0, (snap.buys_5m + snap.sells_5m) / s.score_alive_trades_full)

    if snap.top10_pct is None:
        organic = 0.0
    else:
        organic = min(25.0, max(0.0, 25.0 * (1 - snap.top10_pct / s.top10_max_pct)))

    flush = _flush(snap, s)
    anti_chase = _anti_chase(snap, s)

    if snap.social_score is None:
        social = 0.0
    else:
        social = min(s.social_max_bonus, max(0.0, snap.social_score))

    total = min(100.0, alive + organic + flush + anti_chase + social)
    if total >= s.score_full:
        tier = "full"
    elif total >= s.score_pass:
        tier = "half"
    else:
        tier = "none"
    return ScoreBreakdown(alive, organic, flush, anti_chase, social, total, total >= s.score_pass, tier)


def analyse(snap: TokenSnapshot, settings: Settings) -> tuple[AuditResult, ScoreBreakdown | None]:
    """Audit first. Score only a coin with eight greens (source line 54)."""
    result = audit(snap, settings)
    if not result.passed:
        return result, None
    return result, score(snap, settings)

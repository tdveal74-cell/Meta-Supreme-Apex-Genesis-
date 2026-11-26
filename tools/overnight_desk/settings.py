"""Every number the desk uses, with where it came from and the range it may take.

Three origins, and the difference matters:

- ``doc:N``    the source prompt states the value at line N.
- ``invented`` the source prompt names the thing and gives no value or no
               definition. The default here is a placeholder written for this
               build and waits on the owner's review. See SPEC.md.
- ``owner``    a risk or cost number the source prompt never states. It has NO
               default. The desk refuses to start until the owner sets it.

Every allowed range is invented. The source prompt promises ranges at its
line 16 and gives none.

Standard library only. No clock, no network, no file access outside
``Settings.from_file``.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any


class SettingsError(ValueError):
    """A setting is unknown, missing, of the wrong type or outside its range."""


@dataclass(frozen=True)
class SettingSpec:
    """Origin and allowed range of one setting. ``lo`` and ``hi`` are inclusive."""

    origin: str
    lo: float
    hi: float
    note: str = ""


SPECS: dict[str, SettingSpec] = {
    # --- BOT 1, scanner (source lines 41-42) ---
    "liquidity_floor_usd": SettingSpec(
        "doc:42", 1_000, 10_000_000,
        "kill below this. The figure is the source's; reading 'liquidity' as the value of both sides of the pool is INVENTED",
    ),
    "top10_max_pct": SettingSpec("doc:42", 1, 100, "kill when the top 10 holders hold more than this"),
    "pump_1h_kill_pct": SettingSpec("doc:42", 10, 10_000, "kill at or above this 1 hour gain"),
    "scanner_watch_s": SettingSpec("doc:42", 60, 86_400, "seconds with no kill before a coin passes"),
    "scanner_max_gap_s": SettingSpec(
        "invented", 1, 86_400,
        "a coin unseen for longer than this starts its watch again; the source gives no figure, "
        "and a real feed should set it near its own polling interval",
    ),
    "holders_drop_kill_pct": SettingSpec("invented", 0.1, 100, "'holders leaving' has no definition in the source"),
    # --- BOT 2, analyst (source lines 44-54) ---
    "dev_max_pct": SettingSpec("doc:48", 0, 100, "layer 3: the creator must hold less than this"),
    "lp_locked_min_pct": SettingSpec("doc:50", 0, 100, "layer 5"),
    "pool_age_min_s": SettingSpec("doc:51", 0, 86_400, "layer 6"),
    "bundled_wallets_max": SettingSpec("doc:52", 0, 1_000, "layer 7: fewer than this many bundled wallets"),
    "insiders_max_pct": SettingSpec("doc:52", 0, 100, "layer 7: insiders must hold less than this"),
    "score_pass": SettingSpec("doc:54", 0, 100, "pass at or above"),
    "score_full": SettingSpec("doc:57", 0, 100, "full size at or above; half size from score_pass"),
    "score_alive_trades_full": SettingSpec("invented", 1, 100_000, "trades in 5 minutes that earn the full 'alive' points"),
    "score_antichase_full_below_pct": SettingSpec("invented", 0, 10_000, "1 hour gain at or below which 'anti-chase' is full"),
    "score_flush_full_min_pct": SettingSpec("invented", 0, 100, "pullback from the 10 minute high where 'flush' reaches full"),
    "score_flush_full_max_pct": SettingSpec("invented", 0, 100, "pullback beyond which 'flush' falls to zero"),
    "social_max_bonus": SettingSpec("invented", 0, 30, "most points 'social' may add; it can only raise the score"),
    # --- BOT 3, brain (source lines 56-57) ---
    "risk_per_trade_pct": SettingSpec("doc:57", 0.01, 10, "share of free cash a stop at exactly stop_loss_pct loses"),
    "stop_loss_pct": SettingSpec("doc:57", 1, 90, "the stop below the fill price"),
    "pool_liquidity_cap_pct": SettingSpec(
        "doc:57", 0.01, 10,
        "a ticket may not exceed this share of pool liquidity, both sides counted (that reading is INVENTED)",
    ),
    "min_ticket_usd": SettingSpec("invented", 0.01, 10_000, "skip a ticket smaller than this"),
    "max_ticket_usd": SettingSpec("owner", 0.01, 100_000, "named at source line 57 with no value"),
    "max_open_positions": SettingSpec("owner", 1, 1_000, "the source sets no limit on how many positions are open at once"),
    "max_total_exposure_pct": SettingSpec("owner", 0.1, 100, "cost of open positions as a share of equity"),
    # --- BOT 4, executor (source lines 59-60, 68) ---
    "dip_from_high_pct": SettingSpec("doc:60", 1, 90, "buy only this far below the 10 minute high"),
    "dip_age_min_s": SettingSpec("doc:68", 0, 86_400, "DIP strategy: youngest pool"),
    "dip_age_max_s": SettingSpec("doc:68", 60, 604_800, "DIP strategy: oldest pool"),
    "sell_dryup_ratio": SettingSpec("invented", 0.01, 1, "'sellers drying up': latest 5 minute sell volume against the 5 minutes before"),
    "recheck_max_price_drift_pct": SettingSpec("invented", 0.1, 50, "abort when price moved this far since the decision"),
    "max_snapshot_age_s": SettingSpec(
        "invented", 1, 86_400,
        "a buy never acts on a reading older than this, and an exit decided on one is flagged; the source gives no figure",
    ),
    "take_multiple_green": SettingSpec("doc:60", 1.01, 100, "first take, as a multiple of the fill price"),
    "take_multiple_red": SettingSpec("doc:60", 1.01, 100, "first take while the market mode is RED"),
    "take_fraction": SettingSpec("doc:60", 0.01, 1, "share of the position sold at the first take"),
    "trail_green_pct": SettingSpec(
        "invented", 1, 90,
        "the source gives a trail figure only for RED (20) and says RED tightens trails, so this must be wider",
    ),
    "trail_red_pct": SettingSpec("doc:73", 1, 90, "trail below the peak while RED"),
    # --- BOT 5, risk (source lines 62-63, 73) ---
    "dead_money_after_s": SettingSpec("doc:63", 60, 604_800, "seconds held before the dead money test"),
    "dead_money_min_gain_pct": SettingSpec("doc:63", 0, 1_000, "exit when the gain is under this after dead_money_after_s"),
    "liquidity_pull_drop_pct": SettingSpec("invented", 1, 100, "'pulled liquidity': fall from the liquidity seen at entry"),
    "red_time_stop_s": SettingSpec("doc:73", 60, 604_800, "exit a position held this long while RED"),
    "night_stop_pct": SettingSpec("doc:73", 0.1, 100, "halt new buys when the night's loss reaches this share of starting equity"),
    # --- market mode (source lines 76-77) ---
    "red_btc_1h_pct": SettingSpec("doc:77", -100, 0, "RED when Bitcoin's 1 hour change is at or below this"),
    "red_sol_1h_pct": SettingSpec("doc:77", -100, 0, "RED when Solana's 1 hour change is at or below this"),
    "red_fear_greed_max": SettingSpec("doc:77", 0, 100, "RED when the index is at or below this"),
    "quiet_max_graduations_per_hour": SettingSpec("invented", 0, 100_000, "'few graduations' has no number in the source"),
    # --- paper to live (source line 80) ---
    "paper_nights_required": SettingSpec("doc:80", 1, 365, "full PAPER nights before LIVE may be asked for"),
    # --- costs: the source states none ---
    "venue_fee_pct_per_side": SettingSpec("owner", 0, 20, "the trading app's fee on each buy and each sell"),
    "pool_fee_pct_per_side": SettingSpec("owner", 0, 20, "the pool's own fee on each swap"),
    "fixed_fee_usd_per_side": SettingSpec("owner", 0, 1_000, "any flat charge on each buy and each sell"),
}

INT_SETTINGS = frozenset(
    {
        "scanner_watch_s",
        "scanner_max_gap_s",
        "max_snapshot_age_s",
        "pool_age_min_s",
        "bundled_wallets_max",
        "score_alive_trades_full",
        "max_open_positions",
        "dip_age_min_s",
        "dip_age_max_s",
        "dead_money_after_s",
        "red_time_stop_s",
        "red_fear_greed_max",
        "quiet_max_graduations_per_hour",
        "paper_nights_required",
    }
)


@dataclass(frozen=True)
class Settings:
    """The desk's settings. Build one with ``from_dict`` or ``from_file``.

    A setting whose origin is ``owner`` defaults to ``None``. ``from_dict``
    refuses to return a Settings while any of them is still ``None``.
    """

    liquidity_floor_usd: float = 20_000.0
    top10_max_pct: float = 25.0
    pump_1h_kill_pct: float = 200.0
    scanner_watch_s: int = 600
    scanner_max_gap_s: int = 600
    holders_drop_kill_pct: float = 5.0

    dev_max_pct: float = 5.0
    lp_locked_min_pct: float = 99.0
    pool_age_min_s: int = 600
    bundled_wallets_max: int = 5
    insiders_max_pct: float = 15.0
    score_pass: float = 70.0
    score_full: float = 80.0
    score_alive_trades_full: int = 30
    score_antichase_full_below_pct: float = 50.0
    score_flush_full_min_pct: float = 15.0
    score_flush_full_max_pct: float = 40.0
    social_max_bonus: float = 10.0

    risk_per_trade_pct: float = 3.0
    stop_loss_pct: float = 25.0
    pool_liquidity_cap_pct: float = 2.0
    min_ticket_usd: float = 1.0
    max_ticket_usd: float | None = None
    max_open_positions: int | None = None
    max_total_exposure_pct: float | None = None

    dip_from_high_pct: float = 15.0
    dip_age_min_s: int = 600
    dip_age_max_s: int = 21_600
    sell_dryup_ratio: float = 0.5
    recheck_max_price_drift_pct: float = 5.0
    max_snapshot_age_s: int = 120
    take_multiple_green: float = 2.0
    take_multiple_red: float = 1.5
    take_fraction: float = 0.5
    trail_green_pct: float = 25.0
    trail_red_pct: float = 20.0

    dead_money_after_s: int = 10_800
    dead_money_min_gain_pct: float = 5.0
    liquidity_pull_drop_pct: float = 50.0
    red_time_stop_s: int = 5_400
    night_stop_pct: float = 10.0

    red_btc_1h_pct: float = -2.5
    red_sol_1h_pct: float = -4.0
    red_fear_greed_max: int = 20
    quiet_max_graduations_per_hour: int = 5

    paper_nights_required: int = 3

    venue_fee_pct_per_side: float | None = None
    pool_fee_pct_per_side: float | None = None
    fixed_fee_usd_per_side: float | None = None

    @classmethod
    def from_dict(cls, overrides: dict[str, Any] | None = None) -> Settings:
        """Defaults plus ``overrides``, validated. Raises SettingsError."""
        overrides = dict(overrides or {})
        known = {f.name for f in fields(cls)}
        unknown = sorted(set(overrides) - known)
        if unknown:
            raise SettingsError(f"unknown setting(s): {', '.join(unknown)}")
        candidate = cls(**overrides)
        candidate._validate()
        return candidate

    @classmethod
    def from_file(cls, path: str | Path) -> Settings:
        """Read a JSON object of overrides from ``path`` and validate it."""
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SettingsError(f"cannot read settings file {path}: {type(exc).__name__}") from exc
        if not isinstance(data, dict):
            raise SettingsError("a settings file must hold one JSON object")
        return cls.from_dict(data)

    @classmethod
    def for_tests(cls, **overrides: Any) -> Settings:
        """Settings with the owner-only values filled by TEST PLACEHOLDERS.

        The placeholders exist so tests and the demo replay can run. They are
        no recommendation and no default. A real run sets its own.
        """
        placeholders: dict[str, Any] = {
            "max_ticket_usd": 25.0,
            "max_open_positions": 3,
            "max_total_exposure_pct": 36.0,
            "venue_fee_pct_per_side": 0.5,
            "pool_fee_pct_per_side": 1.25,
            "fixed_fee_usd_per_side": 0.0,
        }
        placeholders.update(overrides)
        return cls.from_dict(placeholders)

    def check(self) -> None:
        """Raise SettingsError unless every value is set, in range and consistent.

        ``from_dict`` and ``from_file`` call this. So does the desk when it is
        built, because a Settings can also be made by hand.
        """
        self._validate()

    def _validate(self) -> None:
        problems: list[str] = []
        for f in fields(self):
            spec = SPECS.get(f.name)
            if spec is None:
                problems.append(f"{f.name}: no SettingSpec, so its origin and range are unknown")
                continue
            value = getattr(self, f.name)
            if value is None:
                if spec.origin == "owner":
                    problems.append(f"{f.name}: the owner must set this; it has no default")
                else:
                    problems.append(f"{f.name}: may not be null")
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                problems.append(f"{f.name}: must be a number, got {type(value).__name__}")
                continue
            if value != value or value in (float("inf"), float("-inf")):
                problems.append(f"{f.name}: must be a finite number")
                continue
            if f.name in INT_SETTINGS and (isinstance(value, float) and not value.is_integer()):
                problems.append(f"{f.name}: must be a whole number, got {value}")
                continue
            if not (spec.lo <= value <= spec.hi):
                problems.append(f"{f.name}: {value} is outside the allowed range {spec.lo} to {spec.hi}")
        if not problems:
            if self.score_full < self.score_pass:
                problems.append("score_full must be at or above score_pass")
            if self.dip_age_max_s <= self.dip_age_min_s:
                problems.append("dip_age_max_s must be above dip_age_min_s")
            if self.score_flush_full_max_pct <= self.score_flush_full_min_pct:
                problems.append("score_flush_full_max_pct must be above score_flush_full_min_pct")
            if self.max_ticket_usd is not None and self.max_ticket_usd < self.min_ticket_usd:
                problems.append("max_ticket_usd must be at or above min_ticket_usd")
            # Source line 77: RED tightens takes and trails. Equal figures would tighten nothing.
            if not self.trail_red_pct < self.trail_green_pct:
                problems.append("trail_red_pct must be below trail_green_pct")
            if not self.take_multiple_red < self.take_multiple_green:
                problems.append("take_multiple_red must be below take_multiple_green")
            # A coin at the scanner's kill level must never earn full anti-chase points.
            if not self.score_antichase_full_below_pct < self.pump_1h_kill_pct:
                problems.append("score_antichase_full_below_pct must be below pump_1h_kill_pct")
        if problems:
            raise SettingsError("; ".join(problems))

    def describe(self) -> list[dict[str, Any]]:
        """One row per setting: name, value, origin, range and note."""
        rows = []
        for f in fields(self):
            spec = SPECS[f.name]
            rows.append(
                {
                    "name": f.name,
                    "value": getattr(self, f.name),
                    "origin": spec.origin,
                    "lo": spec.lo,
                    "hi": spec.hi,
                    "note": spec.note,
                }
            )
        return rows


OWNER_SETTINGS = tuple(name for name, spec in SPECS.items() if spec.origin == "owner")
INVENTED_SETTINGS = tuple(name for name, spec in SPECS.items() if spec.origin == "invented")

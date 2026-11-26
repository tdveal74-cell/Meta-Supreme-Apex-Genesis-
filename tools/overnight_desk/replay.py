"""Replay a recorded night through the desk and print the morning report.

A timeline is a JSON Lines file. Each line is one tick:

    {"ts": 1700000000,
     "market": {"btc_change_1h_pct": 0.2, "sol_change_1h_pct": -0.5,
                "fear_greed": 55, "graduations_last_hour": 20},
     "tokens": [{"mint": "...", "symbol": "...", "price_usd": 0.001, ...}]}

``market`` may be null. A token object takes the field names of
``model.TokenSnapshot``; a token without ``ts`` takes the tick's. An unknown
field name is an error, so a typo cannot pass as a missing reading.

Run it from the repository root:

    PYTHONPATH=tools python3 -m overnight_desk.replay \
        --timeline tools/overnight_desk/fixtures/synthetic_night.jsonl \
        --settings tools/overnight_desk/fixtures/settings.test-placeholders.json \
        --cash 1000

This reads two local files and writes to standard output. It opens no
connection and sends no order.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

from .engine import Desk
from .model import MarketSnapshot, TokenSnapshot
from .report import render_morning
from .settings import Settings, SettingsError


class TimelineError(ValueError):
    """A timeline line is malformed."""


@dataclass(frozen=True)
class Frame:
    ts: int
    market: MarketSnapshot | None
    tokens: tuple[TokenSnapshot, ...]


_TOKEN_FIELDS = {f.name for f in fields(TokenSnapshot)}
_MARKET_FIELDS = {f.name for f in fields(MarketSnapshot)}


def parse_frame(obj: Any, where: str = "frame") -> Frame:
    """One decoded JSON object into a Frame. Raises TimelineError."""
    if not isinstance(obj, dict):
        raise TimelineError(f"{where}: must be a JSON object")
    unknown = sorted(set(obj) - {"ts", "market", "tokens"})
    if unknown:
        raise TimelineError(f"{where}: unknown key(s) {', '.join(unknown)}")
    ts = obj.get("ts")
    if isinstance(ts, bool) or not isinstance(ts, int):
        raise TimelineError(f"{where}: 'ts' must be a whole number of seconds")
    market_obj = obj.get("market")
    market: MarketSnapshot | None = None
    if market_obj is not None:
        if not isinstance(market_obj, dict):
            raise TimelineError(f"{where}: 'market' must be an object or null")
        bad = sorted(set(market_obj) - _MARKET_FIELDS)
        if bad:
            raise TimelineError(f"{where}: unknown market field(s) {', '.join(bad)}")
        market = MarketSnapshot(**{"ts": ts, **market_obj})
    tokens_obj = obj.get("tokens", [])
    if not isinstance(tokens_obj, list):
        raise TimelineError(f"{where}: 'tokens' must be a list")
    tokens = []
    for i, tok in enumerate(tokens_obj):
        if not isinstance(tok, dict):
            raise TimelineError(f"{where}: token {i} must be an object")
        bad = sorted(set(tok) - _TOKEN_FIELDS)
        if bad:
            raise TimelineError(f"{where}: token {i} has unknown field(s) {', '.join(bad)}")
        for need in ("mint", "symbol"):
            if not isinstance(tok.get(need), str) or not tok[need]:
                raise TimelineError(f"{where}: token {i} needs a non-empty '{need}'")
        data = {"ts": ts, **tok}
        if "narrative_tags" in data:
            data["narrative_tags"] = tuple(data["narrative_tags"])
        tokens.append(TokenSnapshot(**data))
    return Frame(ts=ts, market=market, tokens=tuple(tokens))


def load_timeline(path: str | Path) -> list[Frame]:
    """Read a JSON Lines timeline. Blank lines are skipped."""
    frames: list[Frame] = []
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise TimelineError(f"cannot read timeline {path}: {type(exc).__name__}") from exc
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            raise TimelineError(f"line {number}: not valid JSON") from exc
        frames.append(parse_frame(obj, where=f"line {number}"))
    return frames


def run(frames: Sequence[Frame], settings: Settings, starting_cash_usd: float) -> dict[str, Any]:
    """Run every frame through a fresh paper Desk and return its night report."""
    desk = Desk(settings, starting_cash_usd)
    for frame in frames:
        desk.tick(frame.ts, frame.market, frame.tokens)
    return desk.night_report()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="overnight_desk.replay",
        description="Replay a recorded night through the paper desk. Sends no order.",
    )
    parser.add_argument("--timeline", required=True, help="JSON Lines file of ticks")
    parser.add_argument("--settings", required=True, help="JSON file of settings, owner values included")
    parser.add_argument("--cash", required=True, type=float, help="starting cash in dollars")
    parser.add_argument("--json", action="store_true", help="print the raw night report as JSON")
    args = parser.parse_args(argv)
    try:
        settings = Settings.from_file(args.settings)
        frames = load_timeline(args.timeline)
        report = run(frames, settings, args.cash)
    except (SettingsError, TimelineError, ValueError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_morning(report, settings.risk_per_trade_pct), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

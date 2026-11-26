"""BOT 1, the scanner: watch every new coin and kill the ones that fail a cheap test.

Comes from source line 42 of the prompt (liquidity floor, top 10 share, 1 hour
pump, copycat names, disabled trading, all as SPEC.md gives them). One Scanner
holds the state of every coin it has seen. A coin is killed on the first kill
rule it trips and a kill is permanent. A coin that has survived the watch with
its three key numbers known is PASSED, and a later observation can still kill
it.

INVENTED, marked as such in SPEC.md: the definition of ``holders_leaving`` and
its threshold ``holders_drop_kill_pct``. The source names "holders leaving" and
defines nothing.

INVENTED too: the gap rule. A coin last seen more than ``scanner_max_gap_s``
before a reading starts its watch again, because the source says a coin "passes
only after 10 minutes with no kill" and gives no way to count time nobody looked.

No clock: the time is always ``snap.ts``. Nothing here reads a network or a file.
"""
from __future__ import annotations

from .model import ScanResult, ScanState, TokenSnapshot
from .settings import Settings


class Scanner:
    """Holds one ScanResult per mint and updates it on each observation."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._results: dict[str, ScanResult] = {}
        self._last_ts: dict[str, int] = {}

    def observe(self, snap: TokenSnapshot) -> ScanResult:
        """Fold one snapshot into the coin's state and return the new state.

        Raises ``ValueError`` when the snapshot is older than the last one seen
        for the same mint. A refused observation changes nothing.
        """
        mint = snap.mint
        last = self._last_ts.get(mint)
        if last is not None and snap.ts < last:
            raise ValueError(f"observation for {mint} at {snap.ts} is older than the last one at {last}")

        previous = self._results.get(mint)
        first_seen = previous.first_seen_ts if previous is not None else snap.ts
        self._last_ts[mint] = snap.ts

        if previous is not None and previous.state is ScanState.KILLED:
            return previous

        restart_gap: int | None = None
        if last is not None and snap.ts - last > self._settings.scanner_max_gap_s:
            first_seen = snap.ts
            restart_gap = snap.ts - last

        result = self._judge(snap, first_seen, restart_gap)
        self._results[mint] = result
        return result

    def result(self, mint: str) -> ScanResult | None:
        """The last result for ``mint``, or None when it was never observed."""
        return self._results.get(mint)

    def _judge(self, snap: TokenSnapshot, first_seen: int, restart_gap: int | None = None) -> ScanResult:
        s = self._settings
        mint = snap.mint

        def kill(code: str, detail: str) -> ScanResult:
            return ScanResult(mint, ScanState.KILLED, first_seen, code, detail)

        if snap.liquidity_usd is not None and snap.liquidity_usd < s.liquidity_floor_usd:
            return kill("liquidity_below_floor", f"liquidity {snap.liquidity_usd:.2f} < {s.liquidity_floor_usd:.2f}")
        if snap.top10_pct is not None and snap.top10_pct > s.top10_max_pct:
            return kill("top10_above_max", f"top10 {snap.top10_pct:.2f} > {s.top10_max_pct:.2f}")
        if snap.change_1h_pct is not None and snap.change_1h_pct >= s.pump_1h_kill_pct:
            return kill("pumped_1h", f"1h change {snap.change_1h_pct:.2f} >= {s.pump_1h_kill_pct:.2f}")
        if isinstance(snap.copycat_of, str) and snap.copycat_of != "":
            return kill("copycat_name", f"copies {snap.copycat_of}")
        if snap.trading_disabled is True:
            return kill("trading_disabled", "trading is disabled")
        if (
            snap.holders is not None
            and snap.holders_prev is not None
            and snap.holders_prev > 0
            and snap.holders < snap.holders_prev * (1 - s.holders_drop_kill_pct / 100)
        ):
            return kill("holders_leaving", f"holders {snap.holders} from {snap.holders_prev}")

        if restart_gap is not None:
            return ScanResult(
                mint, ScanState.WATCHING, first_seen, "watching", f"watch restarted after a gap of {restart_gap} seconds"
            )
        if snap.ts - first_seen < s.scanner_watch_s:
            return ScanResult(mint, ScanState.WATCHING, first_seen, "watching", "watch period not over")
        if snap.liquidity_usd is None or snap.top10_pct is None or snap.change_1h_pct is None:
            return ScanResult(mint, ScanState.WATCHING, first_seen, "waiting_for_data", "a key number is unknown")
        return ScanResult(mint, ScanState.PASSED, first_seen, "passed", "")

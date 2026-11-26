"""The market mode: GREEN, RED or QUIET, and whether it blocks new buys.

Source line 77 (DOC): RED when Bitcoin's or Solana's 1 hour change, or the
fear and greed index, is at or past its limit. Source line 57 and SPEC.md
reading R1: RED blocks every new buy. The QUIET rule ("few graduations") has
no number in the source, so ``quiet_max_graduations_per_hour`` is INVENTED.
INVENTED as well: missing data blocks new buys. The source does not say what
to do without market data; "when in doubt, no trade" (source line 92) is the
reason for blocking.

Pure function. Nothing is mutated, no clock, no network.
"""
from __future__ import annotations

from .model import MarketSnapshot, MarketState, Mode
from .settings import Settings


def assess(market: MarketSnapshot | None, settings: Settings) -> MarketState:
    """Read the market inputs and return the mode and its effect on buys."""
    if market is None:
        return MarketState(
            mode=Mode.GREEN,
            data_ok=False,
            blocks_new_buys=True,
            reasons=("market snapshot missing",),
        )

    reasons: list[str] = []
    red = False
    data_ok = True

    btc = market.btc_change_1h_pct
    if btc is None:
        data_ok = False
        reasons.append("btc_1h missing")
    elif btc <= settings.red_btc_1h_pct:
        red = True
        reasons.append(f"btc_1h {btc:.2f} <= {settings.red_btc_1h_pct:.2f}")

    sol = market.sol_change_1h_pct
    if sol is None:
        data_ok = False
        reasons.append("sol_1h missing")
    elif sol <= settings.red_sol_1h_pct:
        red = True
        reasons.append(f"sol_1h {sol:.2f} <= {settings.red_sol_1h_pct:.2f}")

    fear = market.fear_greed
    if fear is None:
        data_ok = False
        reasons.append("fear_greed missing")
    elif fear <= settings.red_fear_greed_max:
        red = True
        reasons.append(f"fear_greed {fear} <= {settings.red_fear_greed_max}")

    grads = market.graduations_last_hour
    quiet = False
    if grads is None:
        data_ok = False
        reasons.append("graduations missing")
    elif not red and grads <= settings.quiet_max_graduations_per_hour:
        quiet = True
        reasons.append(f"graduations {grads} <= {settings.quiet_max_graduations_per_hour}")

    if red:
        mode = Mode.RED
    elif quiet:
        mode = Mode.QUIET
    else:
        mode = Mode.GREEN

    blocks = mode in (Mode.RED, Mode.QUIET) or not data_ok
    return MarketState(mode=mode, data_ok=data_ok, blocks_new_buys=blocks, reasons=tuple(reasons))

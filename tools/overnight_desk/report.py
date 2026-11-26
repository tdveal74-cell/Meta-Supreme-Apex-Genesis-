"""The morning report: a night's plain data turned into plain text.

Line 94 of the source prompt says what a good first morning
shows: a clear reason for every skip, every loss within 3% of cash with an
autopsy, zero unverified orders and zero rule violations. This report answers
each of those four from the night's data and claims nothing the data does not
hold. A paper fill is never reported as a verified order.

INVENTED, labelled so in SPEC.md: a check that the night gave nothing to test
reads "n/a" and never "pass". A night with no losses did not test the loss
limit, and a paper night did not test order verification.

Coin symbols and names are text someone else chose. Every piece of free text
is escaped before it is printed, so a symbol cannot add a line to the report.
"""
from __future__ import annotations

from typing import Any


def _usd(value: float | None) -> str:
    if value is None:
        return "unknown"
    return f"-${-value:,.2f}" if value < 0 else f"${value:,.2f}"


def _pct(value: float | None) -> str:
    return "unknown" if value is None else f"{value:.2f}%"


def _clean(value: Any) -> str:
    """Text safe to print on one line: anything not printable is escaped."""
    text = str(value)
    return "".join(ch if ch.isprintable() else f"\\u{ord(ch):04x}" for ch in text)


def morning_checks(report: dict[str, Any], risk_per_trade_pct: float) -> list[dict[str, Any]]:
    """The four tests of source line 94, each with a verdict and its evidence.

    ``ok`` is True for a pass, False for a fail and None when the night gave
    the check nothing to test.
    """
    skips = report["skips"]
    unexplained = [s for s in skips if not s["reason_code"]]
    losses = report["losses"]
    open_positions = report["open_positions"]
    open_over = [p for p in open_positions if p["over_budget"]]
    over = [loss for loss in losses if loss["loss_pct_of_cash"] is None or loss["over_budget"]]
    no_autopsy = [loss for loss in losses if not loss.get("exit_reason")]
    no_lesson = [loss for loss in losses if not loss.get("lesson")]
    unverified = report["verification"]["unverified"]
    real = report["real_orders_sent"]
    violations = report["violations"]

    if report["coins_seen"] == 0:
        skip_ok: bool | None = None
        skip_evidence = "no coin was seen, so there was nothing to skip"
    else:
        skip_ok = not unexplained
        skip_evidence = (
            f"{len(skips)} skips recorded, {len(unexplained)} without a reason code. "
            "The desk gives every skip a code when it records it, so this guards the record"
        )

    if not losses and not open_positions:
        loss_ok: bool | None = None
        loss_evidence = "no position closed at a loss and none is open, so the limit was not tested"
    else:
        loss_ok = not over and not no_autopsy and not open_over
        loss_evidence = (
            f"{len(losses)} closed losses, {len(over)} over the limit or unmeasured, "
            f"{len(no_autopsy)} without an exit reason, {len(no_lesson)} with no lesson written; "
            f"{len(open_positions)} still open, {len(open_over)} of them past the limit at the last price"
        )

    if real == 0:
        order_ok: bool | None = None
        order_evidence = "no real order was sent, so order verification was never exercised"
    else:
        order_ok = unverified == 0
        order_evidence = f"{real} real orders sent, {unverified} unverified"

    if report["ticks"] == 0:
        rule_ok: bool | None = None
        rule_evidence = "no tick ran"
    else:
        rule_ok = not violations
        rule_evidence = (
            f"{len(violations)} recorded. The desk records two kinds only: "
            "an exit it could not carry out, and a loss past the limit"
        )

    return [
        {"check": "a reason for every skip", "ok": skip_ok, "evidence": skip_evidence},
        {
            "check": f"every loss within {risk_per_trade_pct:g}% of cash, with an autopsy",
            "ok": loss_ok,
            "evidence": loss_evidence,
        },
        {"check": "zero unverified orders", "ok": order_ok, "evidence": order_evidence},
        {"check": "zero rule violations", "ok": rule_ok, "evidence": rule_evidence},
    ]


_VERDICT = {True: "pass", False: "FAIL", None: "n/a"}


def render_morning(report: dict[str, Any], risk_per_trade_pct: float) -> str:
    """The night as text. Every figure comes from ``report``."""
    lines: list[str] = []
    add = lines.append
    add("OVERNIGHT DESK, MORNING REPORT")
    add(f"Executor: {_clean(report['executor'])}. Real orders sent: {report['real_orders_sent']}.")
    if report["executor"] == "paper":
        add("This was a paper night. No money moved and no order reached any venue.")
    add("")
    add("What the desk saw")
    add(
        f"  {report['ticks']} ticks, {report['snapshots_seen']} readings, "
        f"{report['coins_seen']} different coins"
    )
    if report["ticks"]:
        add(f"  first tick {report['first_ts']}, last tick {report['last_ts']}")
    if report["coins_seen"] == 0:
        add("  NO COIN WAS SEEN. Nothing below was tested by this night.")
    add("")
    add("Account")
    add(f"  starting cash    {_usd(report['starting_cash_usd'])}")
    add(f"  ending equity    {_usd(report['ending_equity_usd'])}")
    add(f"  night result     {_usd(report['night_pnl_usd'])}")
    add(f"  realized         {_usd(report['realized_pnl_usd'])}")
    add(f"  fees paid        {_usd(report['fees_usd'])}")
    add(f"  buys {report['buys']}, sells {report['sells']}, open positions {len(report['open_positions'])}")
    if report["open_positions"]:
        add("  open positions are valued at their last price, before any cost of selling them")
    add("")
    add("The four morning checks (source line 94)")
    for row in morning_checks(report, risk_per_trade_pct):
        add(f"  [{_VERDICT[row['ok']]}] {row['check']}: {row['evidence']}")
    add("")
    add("Not tested by this night")
    untested = []
    if report["real_orders_sent"] == 0:
        untested.append("order verification: no real order was sent")
    if report.get("recheck_source") == "same_snapshot":
        untested.append(
            "price drift between the decision and the order: the desk had one reading per coin per tick"
        )
    if not report.get("venue_checks_supplied"):
        untested.append(
            "venue warnings and disabled trading: no reading carried either, so those checks had nothing to test"
        )
    if not untested:
        add("  nothing listed")
    for item in untested:
        add(f"  {item}")
    add("")
    add("Market mode")
    if not report["mode_log"]:
        add("  no ticks ran")
    for entry in report["mode_log"]:
        why = "; ".join(_clean(r) for r in entry["reasons"]) or "no trip"
        buys = "new buys blocked" if entry["blocks_new_buys"] else "new buys allowed"
        add(f"  {entry['ts']}  {_clean(entry['mode'])}, {buys} ({why})")
    add("")
    add("Fills")
    if not report["fills"]:
        add("  none")
    for fill in report["fills"]:
        tail = f", {_clean(fill['exit_reason'])}" if fill["exit_reason"] else ""
        add(
            f"  {fill['ts']}  {_clean(fill['side']):<4} {_clean(fill['symbol']):<10} "
            f"{_usd(abs(fill['cash_delta_usd']))} at {fill['price']:.10g}, fees {_usd(fill['fees_usd'])}, "
            f"{_clean(fill['verification'])}{tail}"
        )
    add("")
    add("Losses and their autopsies")
    if not report["losses"]:
        add("  none")
    for loss in report["losses"]:
        add(
            f"  {_clean(loss['symbol'])}: {_usd(loss['pnl_usd'])}, {_pct(loss['loss_pct_of_cash'])} of the cash "
            f"held at entry (budget {_usd(loss['budget_usd'])}). Exit: {_clean(loss['exit_reason'])}. "
            f"Lesson written: {_clean(loss['lesson'] or 'none')}"
        )
    add("")
    add("Rule violations")
    if not report["violations"]:
        add("  none")
    for item in report["violations"]:
        add(f"  {item['ts']}  {_clean(item['rule'])} on {_clean(item['symbol'])}: {_clean(item['detail'])}")
    add("")
    add("Alerts")
    if not report["alerts"]:
        add("  none")
    for alert in report["alerts"]:
        add(f"  {_clean(alert)}")
    add("")
    add("Skips by stage and reason (a coin counts again only when its reason changes)")
    if not report["skips_by_reason"]:
        add("  none")
    first: dict[str, dict[str, Any]] = {}
    for skip in report["skips"]:
        first.setdefault(f"{skip['stage']}:{skip['reason_code']}", skip)
    for key, count in report["skips_by_reason"].items():
        add(f"  {count:>4}  {_clean(key)}")
        example = first.get(key)
        if example is not None and example.get("detail"):
            add(f"        first: {_clean(example['symbol'])}, {_clean(example['detail'])}")
    add("")
    add("Open positions")
    if not report["open_positions"]:
        add("  none")
    for pos in report["open_positions"]:
        last = pos["last_price"]
        add(
            f"  {_clean(pos['symbol'])}: cost {_usd(pos['cost_usd'])}, stop {pos['stop_price']:.10g}, "
            f"last price {'unknown' if last is None else format(last, '.10g')}, "
            f"last reading {'never' if pos.get('last_reading_ts') is None else pos['last_reading_ts']}, "
            f"result so far {_usd(pos['result_so_far_usd'])}"
            f"{', PAST THE LOSS LIMIT' if pos['over_budget'] else ''}"
        )
    add("")
    add("Lessons in force")
    if not report["lessons"]:
        add("  none")
    for row in report["lessons"]:
        add(f"  {_clean(row.get('check', ''))}  ({_clean(row.get('why', ''))})")
    add("")
    add("Live gate")
    if report["live_gate_blockers"]:
        add("  closed: " + ", ".join(_clean(b) for b in report["live_gate_blockers"]))
    else:
        add("  open")
    return "\n".join(lines) + "\n"

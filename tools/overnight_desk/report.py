"""The morning report: a night's plain data turned into plain text.

The source prompt's last paragraph (line 94) says what a good first morning
shows: a clear reason for every skip, every loss within 3% of cash with an
autopsy, zero unverified orders and zero rule violations. This report answers
each of those four from the night's data and claims nothing the data does not
hold. A paper fill is never reported as a verified order.
"""
from __future__ import annotations

from typing import Any


def _usd(value: float | None) -> str:
    if value is None:
        return "unknown"
    return f"-${-value:,.2f}" if value < 0 else f"${value:,.2f}"


def _pct(value: float | None) -> str:
    return "unknown" if value is None else f"{value:.2f}%"


def morning_checks(report: dict[str, Any], risk_per_trade_pct: float) -> list[dict[str, Any]]:
    """The four tests of source line 94, each with a verdict and its evidence."""
    skips = report["skips"]
    unexplained = [s for s in skips if not s["reason_code"]]
    losses = report["losses"]
    over = [
        loss for loss in losses
        if loss["loss_pct_of_cash"] is None or loss["loss_pct_of_cash"] > risk_per_trade_pct
    ]
    no_autopsy = [loss for loss in losses if not loss.get("exit_reason")]
    unverified = report["verification"]["unverified"]
    violations = report["violations"]
    return [
        {
            "check": "a reason for every skip",
            "ok": not unexplained,
            "evidence": f"{len(skips)} skips recorded, {len(unexplained)} without a reason code",
        },
        {
            "check": f"every loss within {risk_per_trade_pct:g}% of cash, with an autopsy",
            "ok": not over and not no_autopsy,
            "evidence": (
                f"{len(losses)} losses, {len(over)} over the limit or unmeasured, "
                f"{len(no_autopsy)} without an exit reason"
            ),
        },
        {
            "check": "zero unverified orders",
            "ok": unverified == 0,
            "evidence": (
                f"{unverified} unverified. {report['real_orders_sent']} real orders were sent, "
                f"so order verification was {'exercised' if report['real_orders_sent'] else 'never exercised'}"
            ),
        },
        {
            "check": "zero rule violations",
            "ok": not violations,
            "evidence": f"{len(violations)} recorded",
        },
    ]


def render_morning(report: dict[str, Any], risk_per_trade_pct: float) -> str:
    """The night as text. Every figure comes from ``report``."""
    lines: list[str] = []
    add = lines.append
    add("OVERNIGHT DESK, MORNING REPORT")
    add(f"Executor: {report['executor']}. Real orders sent: {report['real_orders_sent']}.")
    if report["executor"] == "paper":
        add("This was a paper night. No money moved and no order reached any venue.")
    add("")
    add("Account")
    add(f"  starting cash    {_usd(report['starting_cash_usd'])}")
    add(f"  ending equity    {_usd(report['ending_equity_usd'])}")
    add(f"  night result     {_usd(report['night_pnl_usd'])}")
    add(f"  realized         {_usd(report['realized_pnl_usd'])}")
    add(f"  fees paid        {_usd(report['fees_usd'])}")
    add(f"  buys {report['buys']}, sells {report['sells']}, open positions {len(report['open_positions'])}")
    add("")
    add("The four morning checks (source line 94)")
    for row in morning_checks(report, risk_per_trade_pct):
        add(f"  [{'pass' if row['ok'] else 'FAIL'}] {row['check']}: {row['evidence']}")
    add("")
    add("Market mode")
    if not report["mode_log"]:
        add("  no ticks ran")
    for entry in report["mode_log"]:
        why = "; ".join(entry["reasons"]) or "no trip"
        buys = "new buys blocked" if entry["blocks_new_buys"] else "new buys allowed"
        add(f"  {entry['ts']}  {entry['mode']}, {buys} ({why})")
    add("")
    add("Fills")
    if not report["fills"]:
        add("  none")
    for fill in report["fills"]:
        tail = f", {fill['exit_reason']}" if fill["exit_reason"] else ""
        add(
            f"  {fill['ts']}  {fill['side']:<4} {fill['symbol']:<10} {_usd(abs(fill['cash_delta_usd']))} "
            f"at {fill['price']:.10g}, fees {_usd(fill['fees_usd'])}, {fill['verification']}{tail}"
        )
    add("")
    add("Losses and their autopsies")
    if not report["losses"]:
        add("  none")
    for loss in report["losses"]:
        add(
            f"  {loss['symbol']}: {_usd(loss['pnl_usd'])}, {_pct(loss['loss_pct_of_cash'])} of the cash held at entry "
            f"(budget {_usd(loss['budget_usd'])}). Exit: {loss['exit_reason']}. "
            f"Lesson written: {loss['lesson'] or 'none'}"
        )
    add("")
    add("Rule violations")
    if not report["violations"]:
        add("  none")
    for item in report["violations"]:
        add(f"  {item['ts']}  {item['rule']} on {item['symbol']}: {item['detail']}")
    add("")
    add("Alerts")
    if not report["alerts"]:
        add("  none")
    for alert in report["alerts"]:
        add(f"  {alert}")
    add("")
    add("Skips, counted by stage and reason")
    if not report["skips_by_reason"]:
        add("  none")
    for key, count in report["skips_by_reason"].items():
        add(f"  {count:>4}  {key}")
    add("")
    add("Open positions")
    if not report["open_positions"]:
        add("  none")
    for pos in report["open_positions"]:
        add(
            f"  {pos['symbol']}: cost {_usd(pos['cost_usd'])}, stop {pos['stop_price']:.10g}, "
            f"last price {pos['last_price'] if pos['last_price'] is not None else 'unknown'}"
        )
    add("")
    add("Lessons in force")
    if not report["lessons"]:
        add("  none")
    for row in report["lessons"]:
        add(f"  {row.get('check', '')}  ({row.get('why', '')})")
    add("")
    add("Live gate")
    if report["live_gate_blockers"]:
        add("  closed: " + ", ".join(report["live_gate_blockers"]))
    else:
        add("  open")
    return "\n".join(lines) + "\n"

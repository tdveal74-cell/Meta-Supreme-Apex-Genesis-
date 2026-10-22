#!/usr/bin/env python3
"""Render the gate ledger as a DEVON RECEIPT in the standing format.

The ledger at .claude/ledger/gate-ledger.jsonl lives in the container, which is
reclaimed after inactivity. DEVON's own capture path is the receipt: one
standard block, filed once, readable by every platform. This script turns the
ledger into that block so a session's outward calls survive the container once the
receipt is filed, the same way every other thread does.

    python3 scripts/ledger_receipt.py                  # the whole ledger
    python3 scripts/ledger_receipt.py --session <id>   # one session

It prints the receipt and writes nothing. Filing is a separate act: paste it
into the Thread Log through the devon-thread-log skill, or post it to
devon-capture, which needs the x-devon-key header. That key is not in this
repository and is not set in the cloud environment, so nothing here can post on
its own. A curl to that webhook is a write to a non-local host, so the gate in
.claude/hooks/gate_ledger.py covers it like any other.

The receipt says what the ledger records and what it does not. It records that a
tool call ran and whether the tool reported success. It does not record that the
effect landed.
"""

import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from services.devon.receipts import Receipt, ReceiptFormat, render_standing, validate  # noqa: E402


def default_ledger():
    base = os.environ.get("CLAUDE_PROJECT_DIR") or ROOT
    return os.path.join(base, ".claude", "ledger", "gate-ledger.jsonl")


def read_rows(path):
    """Returns (rows, corrupt_line_count). Raises FileNotFoundError."""
    rows, corrupt = [], 0
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except ValueError:
                corrupt += 1
                continue
            if isinstance(row, dict) and row.get("event") and row.get("tool"):
                rows.append(row)
            else:
                corrupt += 1
    return rows, corrupt


_SAFE = re.compile(r"[^A-Za-z0-9_:.,+\- ]")


def _clean(value, limit=80):
    """A ledger string goes into a receipt field, so it cannot carry a newline,
    a field label or anything else that would parse back as structure."""
    return _SAFE.sub("_", str(value))[:limit]


def _counts(rows, event, gated=None):
    return Counter(
        _clean(r.get("class") or r.get("tool"))
        for r in rows
        if r.get("event") == event and (gated is None or bool(r.get("gated")) is gated)
    )


def _line(counter):
    return ", ".join("%s %d" % (k, v) for k, v in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0])))


def build_receipt(rows, corrupt, ledger_path, today=None):
    executed = _counts(rows, "executed", gated=True)
    logged_only = _counts(rows, "executed", gated=False)
    failed = _counts(rows, "failed")
    denied = _counts(rows, "gate-deny")
    allowed = _counts(rows, "gate-allow", gated=True)
    sessions = sorted({_clean(r.get("session")) for r in rows if r.get("session")})
    days = sorted({_clean(r.get("ts", ""), 10) for r in rows if r.get("ts")})
    receipt_date = (days[-1] if days else (today or date.today()).isoformat())

    n_exec, n_fail = sum(executed.values()), sum(failed.values())
    n_deny, n_allow = sum(denied.values()), sum(allowed.values())
    n_logged = sum(logged_only.values())

    summary = (
        "The gate ledger holds %d executed gated calls, %d failed calls, %d gate decisions that allowed "
        "a gated call and %d that refused one, across %d session%s on %s."
        % (n_exec, n_fail, n_allow, n_deny, len(sessions), "" if len(sessions) == 1 else "s",
           days[0] if len(days) == 1 else "%s to %s" % (days[0], days[-1]) if days else receipt_date)
    )
    if executed:
        summary += " Executed: %s." % _line(executed)
    if n_logged:
        summary += (
            " Also recorded without a gate (merges, the daily reflection row, local deletes and resets): %s."
            % _line(logged_only)
        )

    open_threads = []
    if denied:
        open_threads.append(
            "%d gated call%s refused (%s). The ledger does not show that each was re-asked on a card."
            % (n_deny, "" if n_deny == 1 else "s", _line(denied))
        )
    if failed:
        open_threads.append("%d call%s failed (%s)." % (n_fail, "" if n_fail == 1 else "s", _line(failed)))
    if not open_threads:
        open_threads.append("none: no refused or failed calls in this ledger")

    unverified = [
        "The ledger records that a tool call ran and that the tool reported success, not that the effect landed.",
        "A call the hook does not classify, such as an inline script or the GitHub file tools, is not in it.",
    ]
    if corrupt:
        unverified.append(
            "%d ledger line%s could not be read and %s skipped." % (corrupt, "" if corrupt == 1 else "s", "was" if corrupt == 1 else "were")
        )

    return Receipt(
        date=receipt_date,
        platform="Claude",
        areas=["Systems"],
        summary=summary,
        decided=[],
        built=[os.path.relpath(ledger_path, ROOT) if ledger_path.startswith(ROOT) else ledger_path],
        open_threads=open_threads,
        files_opened=[ledger_path],
        unverified=unverified,
        source_format=ReceiptFormat.STANDING,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--ledger", default=default_ledger())
    parser.add_argument("--session", default="")
    args = parser.parse_args(argv)

    try:
        rows, corrupt = read_rows(args.ledger)
    except FileNotFoundError:
        sys.stderr.write("no ledger at %s: nothing has been recorded in this container\n" % args.ledger)
        return 2
    if args.session:
        rows = [r for r in rows if r.get("session") == args.session]
    if not rows:
        sys.stderr.write("the ledger holds no rows%s\n" % (" for that session" if args.session else ""))
        return 2

    receipt = build_receipt(rows, corrupt, args.ledger)
    problems = [p for p in validate(receipt) if p.severity == "error"]
    if problems:
        sys.stderr.write("the receipt failed DEVON validation:\n%s\n" % "\n".join(str(p) for p in problems))
        return 3
    sys.stdout.write(render_standing(receipt) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

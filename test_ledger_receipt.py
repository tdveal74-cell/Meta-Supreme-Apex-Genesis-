"""
The ledger rendered as a DEVON receipt, ruled by Tee 2026-10-14.

Standalone: no database, no network. The receipt has to pass the same validator
DEVON applies to every thread, so it can be filed through the normal path.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import subprocess
import sys

from services.devon.receipts import ReceiptFormat, detect_format, parse_receipt, validate

ROOT = pathlib.Path(__file__).parent
SCRIPT = ROOT / "scripts" / "ledger_receipt.py"

spec = importlib.util.spec_from_file_location("ledger_receipt", SCRIPT)
lr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lr)


def row(event, tool="mcp__n8n_vps__publish_workflow", cls="publish_workflow", ts="2026-10-14T12:00:00Z",
        session="s1", **extra):
    return dict({"event": event, "tool": tool, "class": cls, "ts": ts, "session": session,
                 "gated": True, "input": "{}"}, **extra)


def write(tmp_path, rows, extra_lines=()):
    path = tmp_path / "ledger.jsonl"
    path.write_text("\n".join([json.dumps(r) for r in rows] + list(extra_lines)) + "\n")
    return str(path)


def test_the_receipt_is_a_valid_standing_receipt(tmp_path):
    path = write(tmp_path, [
        row("gate-allow"), row("executed"), row("executed", cls="update_workflow"),
        row("gate-deny", cls="execute_workflow", reason="no signal"),
        row("failed", cls="curl_mutating", error="HTTP 402"),
    ])
    rows, corrupt = lr.read_rows(path)
    receipt = lr.build_receipt(rows, corrupt, path)
    assert not [p for p in validate(receipt) if p.severity == "error"]
    text = lr.render_standing(receipt)
    assert detect_format(text) is ReceiptFormat.STANDING
    parsed = parse_receipt(text)
    assert parsed.areas == ["Systems"] and parsed.platform == "Claude"
    assert "2 executed" in parsed.summary and "1 failed" in parsed.summary
    assert "1 that refused" in parsed.summary
    assert any("execute_workflow" in t for t in parsed.open_threads)


def test_the_counts_are_the_ledgers_not_the_scripts(tmp_path):
    rows = [row("executed", cls="a")] * 3 + [row("executed", cls="b")] + [row("gate-deny", cls="a")] * 2
    path = write(tmp_path, rows)
    got, corrupt = lr.read_rows(path)
    receipt = lr.build_receipt(got, corrupt, path)
    assert "a 3, b 1" in receipt.summary
    assert "2 gated calls refused (a 2)" in receipt.open_threads[0]


def test_corrupt_lines_are_counted_and_disclosed(tmp_path):
    path = write(tmp_path, [row("executed")], extra_lines=["{not json", "[]", json.dumps({"event": "x"})])
    rows, corrupt = lr.read_rows(path)
    assert len(rows) == 1 and corrupt == 3
    receipt = lr.build_receipt(rows, corrupt, path)
    assert any("3 ledger lines could not be read" in u for u in receipt.unverified)


def test_a_clean_ledger_still_states_open_honestly(tmp_path):
    path = write(tmp_path, [row("executed")])
    rows, corrupt = lr.read_rows(path)
    receipt = lr.build_receipt(rows, corrupt, path)
    assert receipt.open_threads[0].startswith("none:")


def test_the_receipt_says_what_the_ledger_cannot_prove(tmp_path):
    path = write(tmp_path, [row("executed")])
    rows, corrupt = lr.read_rows(path)
    joined = " ".join(lr.build_receipt(rows, corrupt, path).unverified)
    assert "not that the effect landed" in joined and "inline script" in joined


def test_session_filter(tmp_path):
    path = write(tmp_path, [row("executed", session="a"), row("executed", session="b"), row("executed", session="b")])
    proc = subprocess.run([sys.executable, str(SCRIPT), "--ledger", path, "--session", "b"],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert "2 executed" in proc.stdout and "1 session" in proc.stdout


def test_no_ledger_is_exit_two_and_says_so(tmp_path):
    proc = subprocess.run([sys.executable, str(SCRIPT), "--ledger", str(tmp_path / "none.jsonl")],
                          capture_output=True, text=True)
    assert proc.returncode == 2 and "nothing has been recorded" in proc.stderr and proc.stdout == ""


def test_an_empty_session_is_exit_two(tmp_path):
    path = write(tmp_path, [row("executed", session="a")])
    proc = subprocess.run([sys.executable, str(SCRIPT), "--ledger", path, "--session", "zzz"],
                          capture_output=True, text=True)
    assert proc.returncode == 2 and proc.stdout == ""


def test_the_script_writes_nothing(tmp_path):
    path = write(tmp_path, [row("executed")])
    before = sorted(p.name for p in tmp_path.iterdir())
    subprocess.run([sys.executable, str(SCRIPT), "--ledger", path], capture_output=True, text=True)
    assert sorted(p.name for p in tmp_path.iterdir()) == before


def test_the_script_holds_no_secret_and_makes_no_network_call():
    import ast
    tree = ast.parse(SCRIPT.read_text())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    assert not imported & {"urllib", "requests", "socket", "http", "httpx", "subprocess"}, imported
    assert "dcp_" not in SCRIPT.read_text()

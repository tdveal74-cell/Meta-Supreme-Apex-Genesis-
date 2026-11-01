"""Offline tests for scripts/automation_registry.py.

These prove the shape check, the diff and the exit codes against fixtures.
They prove nothing about the key or the host: only a real run of
`--check` with N8N_VPS_KEY set does that.
"""

import json
import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts"))

import automation_registry as reg  # noqa: E402

TODAY = date(2026, 10, 31)


def doc(*rows, every=90):
    return {"review_every_days": every, "workflows": list(rows)}


def row(wid="a1", name="Lane A", reviewed=None, owner="Tee", lane="DEVON"):
    return {"id": wid, "name": name, "lane": lane, "owner": owner, "reviewed": reviewed}


def live(wid="a1", name="Lane A", active=True, updated="2026-09-01T00:00:00.000Z"):
    return {"id": wid, "name": name, "active": active, "updatedAt": updated}


def test_the_shipped_registry_is_well_formed():
    shipped = reg.load()
    assert reg.validate(shipped) == []
    assert len(shipped["workflows"]) == 68
    assert all(r["owner"] == "Tee" for r in shipped["workflows"])


def test_the_shipped_registry_records_no_invented_review_date():
    # Seeded 2026-10-31 with no reviews on record. A date appearing here is a
    # person's act, made in a later commit, never part of the seed.
    assert all(r["reviewed"] is None for r in reg.load()["workflows"])


@pytest.mark.parametrize(
    "bad, fragment",
    [
        ([], "not a JSON object"),
        ({"review_every_days": 0, "workflows": []}, "review_every_days"),
        ({"review_every_days": True, "workflows": []}, "review_every_days"),
        ({"review_every_days": 90, "workflows": {}}, "must be a list"),
        (doc({**row(), "reveiwed": None}), "wrong fields"),
        (doc({k: v for k, v in row().items() if k != "owner"}), "wrong fields"),
        (doc(row(owner=" ")), "empty owner"),
        (doc(row(reviewed="31/10/2026")), "YYYY-MM-DD"),
        (doc(row(reviewed="2026-02-30")), "not a real date"),
        (doc(row(), row()), "repeats id"),
    ],
)
def test_validate_refuses_a_malformed_registry(bad, fragment):
    problems = reg.validate(bad)
    assert any(fragment in p for p in problems), problems


def test_a_matching_estate_is_clean_and_counts_the_backlog():
    findings, notes = reg.diff(doc(row()), [live()], TODAY)
    assert findings == []
    assert notes == ["NEVER REVIEWED: 1 of 1 rows carry no review date"]


def test_an_active_workflow_with_no_row_is_unowned():
    findings, _ = reg.diff(doc(row()), [live(), live("b2", "New lane")], TODAY)
    assert findings == ['UNOWNED: active workflow b2 "New lane" has no row']


def test_an_inactive_workflow_with_no_row_is_not_a_finding():
    findings, _ = reg.diff(doc(row()), [live(), live("b2", "Draft", active=False)], TODAY)
    assert findings == []


def test_a_row_for_a_deleted_or_deactivated_workflow_is_stale():
    findings, _ = reg.diff(doc(row(), row("b2", "Gone")), [live()], TODAY)
    assert findings == ['STALE: b2 "Gone" is not on the instance']
    findings, _ = reg.diff(doc(row()), [live(active=False)], TODAY)
    assert findings == ['STALE: a1 "Lane A" is on the instance but not active']


def test_a_review_older_than_the_period_is_due():
    findings, _ = reg.diff(doc(row(reviewed="2026-08-01")), [live(updated="2026-07-01T00:00:00Z")], TODAY)
    assert len(findings) == 1 and findings[0].startswith("REVIEW DUE") and "91 days ago" in findings[0]


def test_the_period_boundary_is_inclusive():
    findings, _ = reg.diff(doc(row(reviewed="2026-08-02")), [live(updated="2026-07-01T00:00:00Z")], TODAY)
    assert findings == []


def test_a_change_after_the_review_makes_it_due():
    findings, _ = reg.diff(doc(row(reviewed="2026-10-01")), [live(updated="2026-10-20T09:00:00Z")], TODAY)
    assert findings == [
        'REVIEW DUE: a1 "Lane A" owner Tee, changed 2026-10-20 after its review on 2026-10-01'
    ]


def test_a_change_on_the_review_day_is_covered_by_it():
    findings, _ = reg.diff(doc(row(reviewed="2026-10-20")), [live(updated="2026-10-20T23:59:00Z")], TODAY)
    assert findings == []


def test_a_rename_is_a_note_not_a_finding():
    findings, notes = reg.diff(doc(row()), [live(name="Lane A v2")], TODAY)
    assert findings == []
    assert 'RENAMED: a1 is now "Lane A v2", the row says "Lane A"' in notes


def test_check_without_a_key_cannot_check(monkeypatch, capsys):
    monkeypatch.delenv("N8N_VPS_KEY", raising=False)
    assert reg.main(["--check"]) == reg.CANNOT_CHECK
    assert "N8N_VPS_KEY is not set" in capsys.readouterr().out


def test_validate_mode_needs_no_network(monkeypatch):
    monkeypatch.delenv("N8N_VPS_KEY", raising=False)
    assert reg.main(["--validate"]) == reg.OK


def test_an_invalid_file_is_a_finding_before_any_read(tmp_path, monkeypatch):
    path = tmp_path / "r.json"
    path.write_text(json.dumps(doc(row(), row())))
    monkeypatch.setenv("N8N_VPS_KEY", "never-used")
    monkeypatch.setattr(reg, "fetch_workflows", lambda *a: pytest.fail("read before validating"))
    assert reg.main(["--check", "--registry", str(path)]) == reg.FINDING


def test_check_exit_codes_follow_the_diff(tmp_path, monkeypatch):
    path = tmp_path / "r.json"
    path.write_text(json.dumps(doc(row())))
    monkeypatch.setenv("N8N_VPS_KEY", "fixture")
    monkeypatch.setattr(reg, "fetch_workflows", lambda *a: [live()])
    assert reg.main(["--check", "--registry", str(path)]) == reg.OK
    monkeypatch.setattr(reg, "fetch_workflows", lambda *a: [live(), live("b2", "New")])
    assert reg.main(["--check", "--registry", str(path)]) == reg.FINDING


def test_a_failed_read_cannot_check(tmp_path, monkeypatch):
    path = tmp_path / "r.json"
    path.write_text(json.dumps(doc(row())))
    monkeypatch.setenv("N8N_VPS_KEY", "fixture")

    def boom(*_):
        raise ValueError("the workflow listing still had a cursor after 20 pages")

    monkeypatch.setattr(reg, "fetch_workflows", boom)
    assert reg.main(["--check", "--registry", str(path)]) == reg.CANNOT_CHECK


def test_fetch_follows_the_cursor_and_refuses_a_partial_listing(monkeypatch):
    pages = [
        {"data": [{"id": "a1", "name": "A", "active": True, "updatedAt": "x", "nodes": []}], "nextCursor": "c1"},
        {"data": [{"id": "b2", "name": "B", "active": False, "updatedAt": "y"}], "nextCursor": None},
    ]
    seen = []

    class Response:
        def __init__(self, body):
            self.body = json.dumps(body).encode()

        def read(self, *_):
            return self.body

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    def fake_urlopen(request, timeout):
        seen.append(request.full_url)
        return Response(pages[len(seen) - 1])

    monkeypatch.setattr(reg.urllib.request, "urlopen", fake_urlopen)
    out = reg.fetch_workflows("https://host", "k")
    assert [w["id"] for w in out] == ["a1", "b2"]
    assert "nodes" not in out[0]
    assert "cursor=c1" in seen[1]

    endless = {"data": [], "nextCursor": "again"}
    monkeypatch.setattr(reg.urllib.request, "urlopen", lambda r, timeout: Response(endless))
    with pytest.raises(ValueError, match="still had a cursor"):
        reg.fetch_workflows("https://host", "k")


def test_a_review_date_in_the_future_is_a_finding():
    # Found by the critic of c7bc739: 2027 typed for 2026 silenced both alarms.
    findings, _ = reg.diff(doc(row(reviewed="2027-01-01")), [live()], TODAY)
    assert len(findings) == 1 and findings[0].startswith("BAD REVIEW DATE")


def test_a_review_dated_today_is_not_in_the_future():
    findings, _ = reg.diff(doc(row(reviewed="2026-10-31")), [live()], TODAY)
    assert findings == []


def test_the_listing_request_uses_only_parameters_the_watchdogs_already_use():
    # excludePinnedData was in the first version and is used nowhere else in
    # the repository, so it was unproven against the live API and dropped.
    import inspect
    source = inspect.getsource(reg.fetch_workflows)
    assert "excludePinnedData" not in source
    assert "/api/v1/workflows?limit=100" in source

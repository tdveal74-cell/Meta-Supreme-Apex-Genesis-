"""The n8n Data Table name collision detector, and the heartbeat's feeder rule.

Both guard faults that were SILENT in production on 2026-09-16, which is why
each test below drives the real historical data rather than a convenient shape.
"""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

import pytest

from services.devon.data_tables import containment_collisions, describe_collisions

REPO = pathlib.Path(__file__).parent
CHECKER = REPO / "scripts" / "n8n_table_collision_check.py"
PULSE = REPO / "n8n" / "devon" / "heartbeat" / "compose_pulse.js"

#: The VPS project as it stood at 2026-09-15T23:38Z, the minute the TQO lane
#: went quiet. Two mirrors had just been created carrying an existing table's
#: name inside their own.
AT_THE_COLLISION = ["tqo_content", "nco_content", "at_tqo_content", "at_tqo_content_primitives"]

#: The same project after Tee's rename ruling of 2026-09-16, which is the shape
#: a live read returned at 07:25Z that day.
AFTER_THE_RENAME = ["tqo_content", "nco_content", "at_tqo_show_content", "at_tqo_primitives"]


def test_the_detector_finds_the_collision_that_actually_broke_the_lane() -> None:
    collisions = containment_collisions(AT_THE_COLLISION)
    assert ("tqo_content", "at_tqo_content") in collisions
    assert ("tqo_content", "at_tqo_content_primitives") in collisions
    # nco_content was shadowed by nothing, which is why the NCO half kept
    # working and the whole thing read as intermittent.
    assert not [pair for pair in collisions if pair[0] == "nco_content"]


def test_the_rename_that_tee_ruled_actually_clears_it() -> None:
    assert containment_collisions(AFTER_THE_RENAME) == []


def test_a_name_never_collides_with_itself_and_blanks_are_ignored() -> None:
    """Anti vacuity. Equality is not the hazard (n8n refuses duplicate names),
    and an empty string is inside every string, so either one would fill the
    report with noise and bury the real pair."""
    assert containment_collisions(["tqo_content", "tqo_content"]) == []
    assert containment_collisions(["tqo_content", "", "   "]) == []


def test_the_report_names_the_unreachable_table_and_not_just_the_pair() -> None:
    text = describe_collisions(containment_collisions(["tqo_content", "at_tqo_content"]))
    assert "'tqo_content' is contained in 'at_tqo_content'" in text
    assert "return the wrong rows, or none" in text


def _run_checker(payload: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CHECKER)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
    )


def test_the_checker_passes_a_clean_estate_and_fails_the_broken_one() -> None:
    clean = _run_checker([{"name": n} for n in AFTER_THE_RENAME])
    assert clean.returncode == 0, clean.stderr
    assert "no containment collisions" in clean.stdout

    broken = _run_checker({"data": [{"name": n} for n in AT_THE_COLLISION]})
    assert broken.returncode == 1
    assert "at_tqo_content" in broken.stderr
    assert "Rename the LONGER table" in broken.stderr


def test_the_checker_refuses_rather_than_reporting_an_unreadable_estate_safe() -> None:
    """The failure that matters most: a check that cannot see the estate must
    never exit 0. Exit 2 is a third answer on purpose."""
    for payload in ({"data": []}, [], {"tables": "oops"}):
        result = _run_checker(payload)
        assert result.returncode == 2, f"{payload!r} produced {result.returncode}, not a refusal"

    not_json = subprocess.run(
        [sys.executable, str(CHECKER)], input="not json at all",
        capture_output=True, text=True,
    )
    assert not_json.returncode == 2, not_json.stderr


def test_a_mistyped_path_refuses_rather_than_raising_the_alarm_code() -> None:
    """Exit 1 means collisions were found. An unreadable file must not borrow
    that code: it reports a fault that was never looked for, and the next reader
    goes hunting a rename that nothing needs."""
    result = subprocess.run(
        [sys.executable, str(CHECKER), str(REPO / "no_such_tables.json")],
        capture_output=True, text=True,
    )
    assert result.returncode == 2, result.stderr or result.stdout
    assert "could not read table names" in result.stderr


@pytest.mark.parametrize(
    "pattern, why",
    [
        (r"finding\(\s*'feeder_down'", "the dead feeder finding"),
        (r"finding\(\s*'feeder_skipped'", "the passed-over job finding"),
        (r"const FEEDER_PERIOD_H = 24", "the feeder's real daily period"),
    ],
)
def test_the_pulse_carries_the_split_feeder_rule(pattern: str, why: str) -> None:
    assert re.search(pattern, PULSE.read_text()), f"{why} is missing from the Pulse"


def test_the_forty_minute_rule_is_gone_from_the_code_but_not_from_the_history() -> None:
    """Ruled by measurement 2026-09-16. `feeder_silent` fired on the 04:00:15Z
    beat against a feeder that was armed and simply not due until 06:00Z, and it
    could not see a feeder that died on a quiet week. Both names stay in the
    comment so nobody re-derives the forty minutes; neither may stay in the code.
    """
    source = PULSE.read_text()
    assert not re.search(r"finding\(\s*'feeder_silent'", source)
    assert not re.search(r"^\s*const UNFED_MIN", source, re.MULTILINE)
    assert "feeder_silent" in source, "the retirement history is the useful part; keep it"


# ---------------------------------------------------------------------------
# Counting the exposure from the estate, which Tee ruled the arc must carry
# ---------------------------------------------------------------------------
#
# The collision check asks whether a colliding NAME exists today. This asks how
# many locators one could reach at all, which is the number that shrinks
# permanently. It exists because that count drifted twice, eleven then thirteen
# then fifteen, every time it was taken from a dependency list rather than from
# the workflows themselves.


def _dt(name: str, mode: str | None, value: str = "tqo_content") -> dict:
    locator = None if mode is None else {"__rl": True, "mode": mode, "value": value}
    return {
        "name": name,
        "type": "n8n-nodes-base.dataTable",
        "parameters": {"dataTableId": locator} if locator else {},
    }


def _wf(name: str, active: bool, nodes: list[dict], wf_id: str | None = None) -> dict:
    return {"id": wf_id or name, "name": name, "active": active, "nodes": nodes}


def test_only_name_mode_counts_as_exposure():
    """list mode stores an id and resolves like one; no mode names no table."""
    from services.devon.data_tables import name_mode_locators

    found = name_mode_locators(
        [
            _wf(
                "Mixed",
                True,
                [
                    _dt("by name", "name"),
                    _dt("by id", "id", "2GtmrFcTNqVMbddh"),
                    _dt("by list", "list", "2GtmrFcTNqVMbddh"),
                    _dt("creates a table", None),
                    {"name": "not a data table", "type": "n8n-nodes-base.code", "parameters": {}},
                ],
            )
        ]
    )
    assert [record["node"] for record in found] == ["by name"]


def test_active_exposure_sorts_ahead_of_inactive():
    """An active workflow on name mode can bite today. An inactive one cannot."""
    from services.devon.data_tables import describe_name_mode, name_mode_locators

    found = name_mode_locators(
        [
            _wf("Sleeping", False, [_dt("z node", "name")]),
            _wf("Running", True, [_dt("a node", "name")]),
        ]
    )
    assert found[0]["workflow"] == "Running"
    assert found[0]["active"] is True

    report = describe_name_mode(found)
    assert "1 locator(s) resolve by NAME in ACTIVE workflows" in report
    assert "Running :: a node" in report
    assert "1 more sit in inactive workflows" in report


def test_the_clean_report_says_so_rather_than_saying_nothing():
    from services.devon.data_tables import describe_name_mode, name_mode_locators

    report = describe_name_mode(name_mode_locators([_wf("Clean", True, [_dt("ok", "id")])]))
    assert report == "No ACTIVE workflow resolves a Data Table by name."


def _run_check(*args: str):
    import pathlib
    import subprocess
    import sys

    return subprocess.run(
        [sys.executable, "scripts/n8n_name_mode_check.py", *args],
        capture_output=True,
        text=True,
        cwd=pathlib.Path(__file__).parent,
    )


def test_the_check_bites_on_an_active_name_mode_locator(tmp_path):
    import json

    estate = tmp_path / "estate"
    estate.mkdir()
    (estate / "live.json").write_text(json.dumps(_wf("Live One", True, [_dt("Scan", "name")])))
    done = _run_check(str(estate))
    assert done.returncode == 1, done.stdout
    assert "Live One :: Scan" in done.stdout
    assert "1 ACTIVE name mode locator" in done.stderr


def test_the_check_passes_an_estate_whose_active_workflows_are_all_on_id(tmp_path):
    """Inactive exposure is reported and does NOT fail the check.

    It is a loaded gun rather than a fired one. Failing on it would make the
    check permanently red and therefore permanently ignored, which is how a
    guard stops being a guard.
    """
    import json

    estate = tmp_path / "estate"
    estate.mkdir()
    (estate / "live.json").write_text(json.dumps(_wf("Live", True, [_dt("Scan", "id", "abc")])))
    (estate / "idle.json").write_text(json.dumps(_wf("Idle", False, [_dt("Old", "name")])))
    done = _run_check(str(estate))
    assert done.returncode == 0, done.stderr
    assert "No ACTIVE workflow resolves a Data Table by name." in done.stdout
    assert "1 more sit in inactive workflows" in done.stdout


def test_the_export_index_does_not_double_the_count(tmp_path):
    """The export writes a per-workflow file AND an index carrying them all."""
    import json

    estate = tmp_path / "estate"
    estate.mkdir()
    one = _wf("Only", True, [_dt("Scan", "id", "abc")], wf_id="w1")
    (estate / "w1.json").write_text(json.dumps(one))
    (estate / "_index.json").write_text(json.dumps({"data": [one]}))
    done = _run_check(str(estate))
    assert done.returncode == 0, done.stderr
    assert "1 workflow(s) read" in done.stdout


def test_an_unreadable_estate_is_exit_2_and_never_exit_0(tmp_path):
    """The third answer. A check that cannot see the estate must not clear it."""
    missing = _run_check(str(tmp_path / "nope"))
    assert missing.returncode == 2
    assert "NOT reporting the estate clean" in missing.stderr

    empty = tmp_path / "empty"
    empty.mkdir()
    assert _run_check(str(empty)).returncode == 2

    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "bad.json").write_text("{not json")
    assert _run_check(str(broken)).returncode == 2

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

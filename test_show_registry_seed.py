"""The seed script's diff is the only thing that makes its CLEAN mean anything.

`scripts/show_registry_seed.py` reads the two registry tables back and diffs
them against `services/devon/show_registry.py`. These tests feed that diff
fixture rows shaped like the instance's `GET /data-tables/{id}/rows` payload
(system columns included) and prove it reports a missing row, a drifted
value, a duplicate and a stranger, and reports nothing on a faithful copy.
No network: the script's HTTP calls are never reached here.
"""

from __future__ import annotations

import importlib.util
import pathlib

from services.devon.show_registry import REGISTRY_TABLES, registry_rows, series_rows

SCRIPT = pathlib.Path(__file__).resolve().parent / "scripts" / "show_registry_seed.py"


def _seed():
    spec = importlib.util.spec_from_file_location("show_registry_seed", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _as_table(rows):
    return [{"id": index + 1, "createdAt": "2026-10-06T16:00:00.000Z", "updatedAt": "2026-10-06T16:00:00.000Z", **row} for index, row in enumerate(rows)]


def test_a_faithful_table_reads_clean_for_both_tables():
    seed = _seed()
    for table, rows in (("show_registry", registry_rows()), ("show_series", series_rows())):
        missing, problems = seed.diff(table, _as_table(rows))
        assert missing == [] and problems == [], (table, missing, problems)


def test_an_empty_table_wants_every_row():
    seed = _seed()
    missing, problems = seed.diff("show_series", [])
    assert problems == []
    assert [(row["show"], row["key"]) for row in missing] == [(row["show"], row["key"]) for row in series_rows()]
    assert len(missing) == 16


def test_a_drifted_value_is_reported_and_never_rewritten():
    seed = _seed()
    rows = _as_table(registry_rows())
    rows[1]["tagline"] = "Military Mindset. Civilian Impact."
    missing, problems = seed.diff("show_registry", rows)
    assert missing == []
    assert problems == ["show_registry: ('nco',) tagline: table 'Military Mindset. Civilian Impact.', module \"Leaders aren't born. They're forged.\""]


def test_a_duplicate_and_a_stranger_are_both_named():
    seed = _seed()
    rows = _as_table(series_rows())
    rows.append(dict(rows[0], id=99))
    rows.append({"id": 100, "show": "tqo", "key": "resume to robot", "position": 9, "canon": "", "role": "", "tier": "", "mandate": "", "alias_of": "", "segment": ""})
    missing, problems = seed.diff("show_series", rows)
    assert missing == []
    assert "show_series: duplicate row ('tqo', 'the ai shift')" in problems
    assert "show_series: row ('tqo', 'resume to robot') is in the table and not in the module" in problems
    assert len(problems) == 2


def test_an_extra_column_on_the_table_is_reported():
    seed = _seed()
    rows = _as_table(registry_rows())
    rows[0]["colour"] = "slate"
    missing, problems = seed.diff("show_registry", rows)
    assert missing == []
    assert problems == ["show_registry: ('tqo',) carries columns the module does not: ['colour']"]


def test_the_script_names_the_same_tables_as_the_module():
    seed = _seed()
    assert set(seed.ROW_KEYS) == set(REGISTRY_TABLES) == {"show_registry", "show_series"}
    assert seed.SYSTEM_COLUMNS == {"id", "createdAt", "updatedAt"}

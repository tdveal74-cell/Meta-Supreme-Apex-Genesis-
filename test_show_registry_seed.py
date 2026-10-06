"""The seed script's diff is the only thing that makes its CLEAN mean anything.

`scripts/show_registry_seed.py` reads the two registry tables back and diffs
them against `services/devon/show_registry.py`. These tests feed that diff
fixture rows shaped like the instance's `GET /data-tables/{id}/rows` payload
(system columns included) and prove it reports a missing row, a drifted
value, a duplicate and a stranger, and reports nothing on a faithful copy.
The main() tests run the whole command against a fake `_api` and prove the
insert is refused when the id behind a `REGISTRY_TABLES` key answers with
another table's name or column set, and goes through when it matches.

The last three drive `main()` itself through a fake instance in place of
`_api`, so the `--seed` path, the read back after the insert and the exit
code are measured rather than read: an empty instance takes every row and
reads back CLEAN, a drifted row is never written to, and an insert the
instance accepts but does not keep still exits 1.
No network: the script's HTTP calls are never reached here.
"""

from __future__ import annotations

import importlib.util
import pathlib

import pytest

from services.devon.show_registry import REGISTRY_TABLES, registry_rows, series_rows

SCRIPT = pathlib.Path(__file__).resolve().parent / "scripts" / "show_registry_seed.py"


@pytest.fixture(autouse=True)
def _no_live_instance(monkeypatch):
    """No test here may reach the n8n instance: with the key unset, a call that
    slips past a fake refuses with SystemExit instead of reading live tables."""
    monkeypatch.delenv("N8N_VPS_KEY", raising=False)
    monkeypatch.delenv("N8N_VPS_URL", raising=False)


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


def _table_payload(table_id, name, column_names):
    """The shape `GET /data-tables/{id}` returned on the live instance on 2026-10-06."""
    return {
        "id": table_id,
        "name": name,
        "projectId": "qbrcjkbIoorbwot6",
        "columns": [{"id": f"c{index}", "dataTableId": table_id, "name": column, "type": "string", "index": index} for index, column in enumerate(column_names)],
    }


def _fake_api(tables):
    """A stand in for the script's `_api`: serves the table definitions and rows in
    `tables` (id -> {"payload": ..., "rows": [...]}) and records every POST as an
    insert into that table's rows, so a test can prove whether the write happened."""
    calls = []

    def api(path, method="GET", body=None):
        calls.append((method, path))
        table_id = path.split("/")[2].split("?")[0]
        entry = tables[table_id]
        if method == "POST":
            entry["rows"].extend(_as_table(body["data"]))
            return {"count": len(body["data"])}
        if path.endswith(f"/data-tables/{table_id}"):
            return entry["payload"]
        return {"data": list(entry["rows"]), "nextCursor": None}

    api.calls = calls
    return api


def _empty_tables(registry_payload=None, series_payload=None):
    registry_id, series_id = REGISTRY_TABLES["show_registry"], REGISTRY_TABLES["show_series"]
    return {
        registry_id: {"payload": registry_payload or _table_payload(registry_id, "show_registry", registry_rows()[0].keys()), "rows": []},
        series_id: {"payload": series_payload or _table_payload(series_id, "show_series", series_rows()[0].keys()), "rows": []},
    }


def _posts(api):
    return [path for method, path in api.calls if method == "POST"]


def test_a_wrong_column_set_blocks_the_post(monkeypatch, capsys):
    seed = _seed()
    registry_id = REGISTRY_TABLES["show_registry"]
    stranger = _table_payload(registry_id, "show_registry", ["title", "slot", "status", "notes"])
    api = _fake_api(_empty_tables(registry_payload=stranger))
    monkeypatch.setattr(seed, "_api", api)
    assert seed.main(["--seed"]) == 1
    out = capsys.readouterr().out
    assert f"show_registry ({registry_id}): columns differ from the module: table only ['notes', 'slot', 'status', 'title'], module only [" in out
    assert f"show_registry ({registry_id}): REFUSED to insert 2 rows" in out
    assert _posts(api) == [f"/data-tables/{REGISTRY_TABLES['show_series']}/rows"], "the registry POST must not happen and the series one still must"


def test_a_wrong_table_name_blocks_the_post(monkeypatch, capsys):
    seed = _seed()
    series_id = REGISTRY_TABLES["show_series"]
    renamed = _table_payload(series_id, "publishing_slots", series_rows()[0].keys())
    api = _fake_api(_empty_tables(series_payload=renamed))
    monkeypatch.setattr(seed, "_api", api)
    assert seed.main(["--seed"]) == 1
    out = capsys.readouterr().out
    assert f"show_series ({series_id}): the table is named 'publishing_slots', not 'show_series'" in out
    assert f"show_series ({series_id}): REFUSED to insert 16 rows" in out
    assert _posts(api) == [f"/data-tables/{REGISTRY_TABLES['show_registry']}/rows"]


def test_a_matching_table_is_seeded_and_reads_back_clean(monkeypatch, capsys):
    seed = _seed()
    api = _fake_api(_empty_tables())
    monkeypatch.setattr(seed, "_api", api)
    assert seed.main(["--seed"]) == 0
    out = capsys.readouterr().out
    assert "REFUSED" not in out
    assert _posts(api) == [f"/data-tables/{table_id}/rows" for table_id in REGISTRY_TABLES.values()]
    assert f"show_registry ({REGISTRY_TABLES['show_registry']}): 2 rows read back, 2 expected, CLEAN" in out
    assert f"show_series ({REGISTRY_TABLES['show_series']}): 16 rows read back, 16 expected, CLEAN" in out


def test_the_guard_reads_the_table_definition_before_every_insert_and_not_otherwise(monkeypatch):
    seed = _seed()
    api = _fake_api(_empty_tables())
    monkeypatch.setattr(seed, "_api", api)
    assert seed.main(["--check"]) == 1
    assert [path for method, path in api.calls if "/rows" not in path] == []
    api.calls.clear()
    assert seed.main(["--seed", "--dry-run"]) == 1
    definitions = [path for method, path in api.calls if "/rows" not in path]
    assert definitions == [f"/data-tables/{table_id}" for table_id in REGISTRY_TABLES.values()]
    assert _posts(api) == []

def _definition(path):
    """The `GET /data-tables/{id}` answer for one of the two registry tables."""
    table_id = path.split("/")[2].split("?")[0]
    name = next(key for key, value in REGISTRY_TABLES.items() if value == table_id)
    columns = (registry_rows() if name == "show_registry" else series_rows())[0]
    return _table_payload(table_id, name, list(columns))


def _fake_instance(seed, tables):
    """Replace the script's HTTP call with an in-memory instance.

    GET on a rows route serves the fixture table in one page; POST appends
    the rows and records the call, so a test can read back exactly what
    `--seed` tried to write.
    """
    posts = []

    def _api(path, method="GET", body=None):
        if method == "GET" and "/rows" not in path:
            return _definition(path)
        table_id = path.split("/")[2]
        if method == "POST":
            posts.append((table_id, body["data"]))
            tables[table_id].extend(body["data"])
            return {"count": len(body["data"])}
        return {"data": list(tables[table_id]), "nextCursor": None}

    seed._api = _api
    return posts


def _drifted_registry():
    """The finding's shape: the identity column of one live row drifted."""
    rows = _as_table(registry_rows())
    rows[1]["key"] = " nco"
    return rows


def test_seed_refuses_to_insert_beside_a_stranger(capsys):
    seed = _seed()
    tables = {REGISTRY_TABLES["show_registry"]: _drifted_registry(), REGISTRY_TABLES["show_series"]: _as_table(series_rows())}
    posts = _fake_instance(seed, tables)
    assert seed.main(["--seed"]) == 1
    assert posts == [], "a table that reads DRIFT must take no insert"
    out = capsys.readouterr().out
    assert "show_registry: row (' nco',) is in the table and not in the module" in out
    assert "show_registry (xmNWLUm49QyZ4ysO): REFUSED to insert 1 rows: the table reads DRIFT" in out
    assert "show_registry (xmNWLUm49QyZ4ysO): 1 rows missing: [('nco',)]" in out
    assert "show_series (s1IxySUuphOVrOqU): 16 rows read back, 16 expected, CLEAN" in out


def test_seed_dry_run_refuses_the_same_way(capsys):
    seed = _seed()
    tables = {REGISTRY_TABLES["show_registry"]: _drifted_registry(), REGISTRY_TABLES["show_series"]: _as_table(series_rows())}
    posts = _fake_instance(seed, tables)
    assert seed.main(["--seed", "--dry-run"]) == 1
    assert posts == []
    out = capsys.readouterr().out
    assert "would insert" not in out
    assert "REFUSED to insert 1 rows" in out


def test_seed_still_inserts_into_a_clean_table_that_lacks_rows(capsys):
    seed = _seed()
    short = _as_table(series_rows())[:-3]
    tables = {REGISTRY_TABLES["show_registry"]: _as_table(registry_rows()), REGISTRY_TABLES["show_series"]: short}
    posts = _fake_instance(seed, tables)
    assert seed.main(["--seed"]) == 0
    assert [(table_id, [(row["show"], row["key"]) for row in rows]) for table_id, rows in posts] == [
        (REGISTRY_TABLES["show_series"], [(row["show"], row["key"]) for row in series_rows()[-3:]])
    ]
    out = capsys.readouterr().out
    assert "REFUSED" not in out
    assert "show_series (s1IxySUuphOVrOqU): 3 of 3 posted rows inserted, proven by read back" in out
    assert "show_series (s1IxySUuphOVrOqU): 16 rows read back, 16 expected, CLEAN" in out


def test_check_on_a_drifted_table_reports_and_writes_nothing(capsys):
    seed = _seed()
    tables = {REGISTRY_TABLES["show_registry"]: _drifted_registry(), REGISTRY_TABLES["show_series"]: _as_table(series_rows())}
    posts = _fake_instance(seed, tables)
    assert seed.main(["--check"]) == 1
    assert posts == []
    out = capsys.readouterr().out
    assert "REFUSED" not in out
    assert "show_registry: row (' nco',) is in the table and not in the module" in out
    assert "show_registry (xmNWLUm49QyZ4ysO): 2 rows read back, 2 expected, DRIFT" in out

def _seed_run(monkeypatch, capsys, landed_after_insert, insert_result):
    """Drive `main(["--seed"])` with both HTTP calls stubbed and return its stdout."""
    seed = _seed()
    read_before = set()

    def read_rows(table_id):
        table = next(name for name, tid in REGISTRY_TABLES.items() if tid == table_id)
        read_back = table_id in read_before
        read_before.add(table_id)
        return _as_table(seed.expected(table)) if landed_after_insert and read_back else []

    monkeypatch.setattr(seed, "read_rows", read_rows)
    monkeypatch.setattr(seed, "insert_rows", lambda table_id, rows: insert_result)
    monkeypatch.setattr(seed, "describe_table", lambda table_id: _definition(f"/data-tables/{table_id}"))
    code = seed.main(["--seed"])
    return code, capsys.readouterr().out


def test_a_seed_the_instance_dropped_never_calls_the_rows_inserted(monkeypatch, capsys):
    code, out = _seed_run(monkeypatch, capsys, landed_after_insert=False, insert_result={"count": 0})
    assert code == 1
    assert "inserted 2 rows" not in out and "inserted 16 rows" not in out
    assert "show_registry (xmNWLUm49QyZ4ysO): posted 2 rows, instance reports count 0" in out
    assert "show_registry (xmNWLUm49QyZ4ysO): 0 of 2 posted rows inserted, proven by read back" in out
    assert "show_series (s1IxySUuphOVrOqU): 0 of 16 posted rows inserted, proven by read back" in out


def test_a_seed_that_landed_is_counted_from_the_read_back_not_the_request(monkeypatch, capsys):
    code, out = _seed_run(monkeypatch, capsys, landed_after_insert=True, insert_result={"count": 2})
    assert code == 0
    assert "show_registry (xmNWLUm49QyZ4ysO): posted 2 rows, instance reports count 2" in out
    assert "show_registry (xmNWLUm49QyZ4ysO): 2 of 2 posted rows inserted, proven by read back" in out
    assert "show_series (s1IxySUuphOVrOqU): 16 of 16 posted rows inserted, proven by read back" in out

class _FakeInstance:
    """Stands in for `_api`: two tables in memory, every call recorded.

    `lose_inserts` makes a POST answer with a count and keep nothing, which is
    the shape of a seed that reports success and writes nothing.
    """

    def __init__(self, tables, lose_inserts=False):
        self.tables = {table_id: list(rows) for table_id, rows in tables.items()}
        self.calls = []
        self.lose_inserts = lose_inserts

    def __call__(self, path, method="GET", body=None):
        self.calls.append((method, path, body))
        if method == "GET" and "/rows" not in path:
            return _definition(path)
        table_id = path.split("/")[2]
        if method == "GET":
            return {"data": list(self.tables[table_id]), "nextCursor": None}
        assert method == "POST", method
        if not self.lose_inserts:
            self.tables[table_id].extend(_as_table(body["data"]))
        return {"count": len(body["data"])}

    def posts(self):
        return [(path, body) for method, path, body in self.calls if method == "POST"]

    def gets(self, table_id):
        return [path for method, path, _ in self.calls if method == "GET" and f"/{table_id}/" in path]


def _run(seed, monkeypatch, instance, argv):
    monkeypatch.setattr(seed, "_api", instance)
    return seed.main(argv)


def test_seed_on_an_empty_instance_inserts_every_row_and_reads_it_back_clean(monkeypatch, capsys):
    seed = _seed()
    instance = _FakeInstance({table_id: [] for table_id in REGISTRY_TABLES.values()})
    assert _run(seed, monkeypatch, instance, ["--seed"]) == 0
    assert instance.posts() == [
        (f"/data-tables/{REGISTRY_TABLES['show_registry']}/rows", {"data": list(registry_rows()), "returnType": "count"}),
        (f"/data-tables/{REGISTRY_TABLES['show_series']}/rows", {"data": list(series_rows()), "returnType": "count"}),
    ]
    for table_id in REGISTRY_TABLES.values():
        assert len(instance.gets(table_id)) == 2, "one read before the insert and one after it"
    out = capsys.readouterr().out
    assert "show_registry (xmNWLUm49QyZ4ysO): 2 rows read back, 2 expected, CLEAN" in out
    assert "show_series (s1IxySUuphOVrOqU): 16 rows read back, 16 expected, CLEAN" in out
    assert "DRIFT" not in out


def test_seed_never_writes_when_a_row_has_drifted(monkeypatch, capsys):
    seed = _seed()
    registry = _as_table(registry_rows())
    registry[1]["tagline"] = "Military Mindset. Civilian Impact."
    instance = _FakeInstance({REGISTRY_TABLES["show_registry"]: registry, REGISTRY_TABLES["show_series"]: _as_table(series_rows())})
    assert _run(seed, monkeypatch, instance, ["--seed"]) == 1
    assert instance.posts() == []
    assert all(method == "GET" for method, _, _ in instance.calls)
    out = capsys.readouterr().out
    assert "show_registry: ('nco',) tagline: table 'Military Mindset. Civilian Impact.'" in out
    assert "show_registry (xmNWLUm49QyZ4ysO): 2 rows read back, 2 expected, DRIFT" in out
    assert "show_series (s1IxySUuphOVrOqU): 16 rows read back, 16 expected, CLEAN" in out


def test_a_read_back_that_still_lacks_rows_after_the_insert_exits_1(monkeypatch, capsys):
    seed = _seed()
    instance = _FakeInstance({table_id: [] for table_id in REGISTRY_TABLES.values()}, lose_inserts=True)
    assert _run(seed, monkeypatch, instance, ["--seed"]) == 1
    assert len(instance.posts()) == 2
    out = capsys.readouterr().out
    assert "show_registry (xmNWLUm49QyZ4ysO): posted 2 rows, instance reports count 2" in out
    assert "show_registry (xmNWLUm49QyZ4ysO): 0 of 2 posted rows inserted, proven by read back" in out
    assert "show_registry (xmNWLUm49QyZ4ysO): 2 rows missing: [('tqo',), ('nco',)]" in out
    assert "show_registry (xmNWLUm49QyZ4ysO): 0 rows read back, 2 expected, DRIFT" in out
    assert "show_series (s1IxySUuphOVrOqU): 16 rows missing:" in out
    assert "CLEAN" not in out


#: Column names and types of the two live tables, read by GET /data-tables/{id}
#: on 2026-10-06 after they were created. The create payload --spec prints must
#: reproduce them, so a lost table is recreated from the module, not from memory.
LIVE_COLUMNS = {"show_registry": [["brand", "string"], ["brief_audience", "string"], ["brief_from_name", "string"], ["brief_mailerlite_group_id", "string"], ["brief_move_label", "string"], ["brief_name", "string"], ["brief_reach_profile_uuid", "string"], ["brief_section_notes", "string"], ["brief_sections", "string"], ["brief_voice", "string"], ["channel", "string"], ["key", "string"], ["kicker", "string"], ["package_limit", "number"], ["positioning", "string"], ["promote_limit", "number"], ["required_tags", "string"], ["script_limit", "number"], ["show", "string"], ["table_id", "string"], ["table_name", "string"], ["tagline", "string"], ["tagline2", "string"], ["thesis", "string"], ["voice_eleven_model", "string"], ["voice_id", "string"], ["voice_provider_eleven", "string"], ["voice_provider_speechify", "string"], ["voice_ready", "boolean"], ["voice_settings", "string"], ["voice_speechify_model", "string"], ["voice_speechify_voice_id", "string"], ["voice_stale_claim_hours", "number"], ["youtube_ready", "boolean"]], "show_series": [["alias_of", "string"], ["canon", "string"], ["key", "string"], ["mandate", "string"], ["position", "number"], ["role", "string"], ["segment", "string"], ["show", "string"], ["tier", "string"]]}


def test_the_create_spec_reproduces_the_live_tables():
    seed = _seed()
    for table in REGISTRY_TABLES:
        spec = seed.column_spec(table)
        assert spec["name"] == table and spec["projectId"] == "qbrcjkbIoorbwot6"
        got = sorted([column["name"], column["type"]] for column in spec["columns"])
        assert got == [list(pair) for pair in LIVE_COLUMNS[table]], table


def test_the_url_defaults_the_way_the_watchdogs_do(monkeypatch):
    seed = _seed()
    seen = []

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return b"{}"

    def _urlopen(request, timeout):
        seen.append(request.full_url)
        return _Response()

    monkeypatch.delenv("N8N_VPS_URL", raising=False)
    monkeypatch.setenv("N8N_VPS_KEY", "k")
    monkeypatch.setattr(seed.urllib.request, "urlopen", _urlopen)
    seed._api("/data-tables/x")
    assert seen == ["https://n8n.editforge.online/api/v1/data-tables/x"]
    monkeypatch.delenv("N8N_VPS_KEY")
    try:
        seed._api("/data-tables/x")
    except SystemExit as error:
        assert "N8N_VPS_KEY" in str(error)
    else:
        raise AssertionError("a missing key must refuse before any request")
    assert len(seen) == 1

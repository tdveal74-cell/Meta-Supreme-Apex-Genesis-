"""scripts/n8n_migrate.py: the parts that decide what a cutover touches.

Everything here runs against a synthetic export in a temp directory and a fake
HTTP layer. The point of each test is a silent failure the tool exists to
make loud: a host literal left inside a Code node, a sub-workflow id that the
export never saw, a credential still bound to a source id after import.
"""

from __future__ import annotations

import argparse
import json
import pathlib

import pytest

from scripts import n8n_migrate as migrate

SOURCE = "source.app.n8n.cloud"
TARGET = "n8n.target.test"


def _workflow_a() -> dict:
    return {
        "id": "wfA",
        "name": "Organ A",
        "active": True,
        "settings": {"executionOrder": "v1", "errorWorkflow": "wfE"},
        "connections": {},
        "nodes": [
            {
                "name": "Door",
                "type": "n8n-nodes-base.webhook",
                "parameters": {"path": "devon-a", "httpMethod": "POST", "authentication": "headerAuth"},
                "credentials": {"httpHeaderAuth": {"id": "cred1", "name": "Devon Capture Key"}},
            },
            {
                "name": "Call B",
                "type": "n8n-nodes-base.httpRequest",
                "parameters": {"url": f"https://{SOURCE}/webhook/devon-b", "method": "POST"},
                "credentials": {"httpHeaderAuth": {"id": "cred1", "name": "Devon Capture Key"}},
            },
            {
                "name": "Decide",
                "type": "n8n-nodes-base.code",
                "parameters": {
                    "jsCode": (
                        f"const HOST = 'https://{SOURCE}/webhook/';\n"
                        f"const ALT = 'https://{SOURCE}/webhook-test/';\n"
                        "const OTHER = 'https://api.airtable.com/v0';\n"
                        "return [{ json: { n: 1 } }];"
                    )
                },
            },
            {
                "name": "Run B",
                "type": "n8n-nodes-base.executeWorkflow",
                "parameters": {"workflowId": {"__rl": True, "mode": "list", "value": "wfB", "cachedResultName": "Organ B"}},
            },
            {
                "name": "Ledger Row",
                "type": "n8n-nodes-base.dataTable",
                "parameters": {"dataTableId": {"__rl": True, "mode": "id", "value": "tbl1"}, "operation": "upsert"},
            },
            {
                "name": "Sticky",
                "type": "n8n-nodes-base.stickyNote",
                "parameters": {"content": f"## Notes\nPosts to https://{SOURCE}/webhook/devon-b"},
            },
        ],
    }


def _workflow_b() -> dict:
    return {
        "id": "wfB",
        "name": "Organ B",
        "active": True,
        "settings": {},
        "connections": {},
        "nodes": [
            {"name": "Start", "type": "n8n-nodes-base.executeWorkflowTrigger", "parameters": {}},
            {
                "name": "Mail",
                "type": "n8n-nodes-base.emailSend",
                "parameters": {"toEmail": "tee@example.test"},
                "credentials": {"smtp": {"id": "cred2", "name": "SMTP account"}},
            },
        ],
    }


def _workflow_c() -> dict:
    return {
        "id": "wfC",
        "name": "Orphan Caller",
        "active": False,
        "settings": {},
        "connections": {},
        "nodes": [
            {
                "name": "Run Z",
                "type": "n8n-nodes-base.executeWorkflow",
                "parameters": {"workflowId": "wfZ"},
            },
            {
                "name": "Air",
                "type": "n8n-nodes-base.airtable",
                "parameters": {"table": {"__rl": True, "mode": "list", "value": "tblAirtable"}},
                "credentials": {"airtableTokenApi": {"id": "cred3", "name": "Airtable PAT"}},
            },
            {
                "name": "Old Table",
                "type": "n8n-nodes-base.dataTable",
                "parameters": {"tableId": "tbl2"},
            },
        ],
    }


@pytest.fixture
def export_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    for data in (_workflow_a(), _workflow_b(), _workflow_c()):
        (tmp_path / migrate._slug(data["name"], data["id"])).write_text(json.dumps(data), encoding="utf-8")
    (tmp_path / "_index.json").write_text("[]", encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------------------
# pure helpers
# ---------------------------------------------------------------------------

def test_strings_walks_every_leaf_with_a_path():
    found = dict(migrate._strings({"a": ["x", {"b": "y"}], "c": 3, "d": None}))
    assert found == {"a[0]": "x", "a[1].b": "y"}


def test_rewrite_counts_every_occurrence_and_leaves_non_strings_alone():
    value = {"url": f"https://{SOURCE}/w", "code": f"'{SOURCE}' + '{SOURCE}'", "n": 7, "ok": True, "list": [SOURCE]}
    out, hits = migrate._rewrite_strings(value, [(SOURCE, TARGET)])
    assert hits == 4
    assert out == {"url": f"https://{TARGET}/w", "code": f"'{TARGET}' + '{TARGET}'", "n": 7, "ok": True, "list": [TARGET]}
    assert value["url"].endswith("/w") and SOURCE in value["url"], "input must not be mutated"


def test_ref_id_reads_bare_strings_and_resource_locators():
    assert migrate._ref_id("abc") == "abc"
    assert migrate._ref_id({"__rl": True, "mode": "id", "value": "xyz"}) == "xyz"
    assert migrate._ref_id({"__rl": True, "mode": "list"}) == ""
    assert migrate._ref_id(None) == ""


def test_set_ref_id_keeps_the_locator_shape_and_refreshes_the_cached_name_and_url():
    locator = {"__rl": True, "mode": "list", "value": "old", "cachedResultName": "Old Name",
               "cachedResultUrl": f"https://{TARGET}/workflow/old"}
    out = migrate._set_ref_id(locator, "old", "new", "New Name")
    assert out == {"__rl": True, "mode": "list", "value": "new", "cachedResultName": "New Name",
                   "cachedResultUrl": f"https://{TARGET}/workflow/new"}
    assert locator["value"] == "old"
    assert migrate._set_ref_id("old", "old", "new", None) == "new"


def test_literal_matcher_is_a_whole_host_and_case_blind():
    hits = migrate._count_literal({
        "a": f"https://{SOURCE}/webhook/x",
        "b": f"my{SOURCE}/x",
        "c": f"{SOURCE}.evil.com",
        "d": f"mail@{SOURCE}",
        "e": f"'{SOURCE.upper()}'",
        "f": f"{SOURCE}",
    }, SOURCE)
    assert hits == 3, "a, e and f only"
    out, n = migrate._rewrite_strings({"b": f"my{SOURCE}/x", "c": f"{SOURCE}.evil.com", "d": f"mail@{SOURCE}"}, [(SOURCE, TARGET)])
    assert n == 0 and SOURCE in out["b"] and SOURCE in out["c"] and SOURCE in out["d"]


def test_load_map_rejects_a_blank_new_id(tmp_path: pathlib.Path):
    for bad in ({"cred1": ""}, {"cred1": "   "}, {"cred1": {"id": "", "name": "x"}}):
        path = tmp_path / "map.json"
        path.write_text(json.dumps(bad), encoding="utf-8")
        with pytest.raises(SystemExit, match="non-empty"):
            migrate._load_map(str(path))


def test_parse_pairs_rejects_half_a_pair():
    assert migrate._parse_pairs([f"{SOURCE}={TARGET}"]) == [(SOURCE, TARGET)]
    with pytest.raises(SystemExit):
        migrate._parse_pairs(["nohost"])
    with pytest.raises(SystemExit):
        migrate._parse_pairs(["=target"])


def test_load_map_accepts_both_shapes(tmp_path: pathlib.Path):
    path = tmp_path / "map.json"
    path.write_text(json.dumps({"old1": "new1", "old2": {"id": "new2", "name": "Two"}}), encoding="utf-8")
    assert migrate._load_map(str(path)) == {
        "old1": {"id": "new1", "name": None},
        "old2": {"id": "new2", "name": "Two"},
    }
    assert migrate._load_map(None) == {}


# ---------------------------------------------------------------------------
# scan and inspect
# ---------------------------------------------------------------------------

def test_scan_counts_host_literals_per_node_and_keeps_sticky_notes_apart(export_dir):
    scan = migrate._scan(export_dir)
    hosts = scan.hosts[SOURCE]
    assert sorted(hosts) == [("Organ A", "Call B", 1), ("Organ A", "Decide", 2)]
    assert scan.hosts["api.airtable.com"] == [("Organ A", "Decide", 1)]
    assert scan.sticky_hosts[SOURCE] == [("Organ A", "Sticky", 1)]


def test_scan_finds_sub_workflow_targets_error_workflows_credentials_and_tables(export_dir):
    scan = migrate._scan(export_dir)
    assert scan.sub_targets == {"wfB": [("Organ A", "Run B")], "wfZ": [("Orphan Caller", "Run Z")]}
    assert scan.error_workflows == {"wfE": ["Organ A"]}
    assert scan.ids == {"wfA", "wfB", "wfC"}
    assert scan.credentials["cred1"] == {"name": "Devon Capture Key", "types": {"httpHeaderAuth"}}
    assert scan.credentials["cred2"]["types"] == {"smtp"}
    assert scan.credentials["cred3"]["types"] == {"airtableTokenApi"}
    # An Airtable node's table is not an n8n data table; a data table node's is.
    assert set(scan.tables) == {"tbl1", "tbl2"}
    assert scan.webhooks == {"devon-a": ["Organ A"]}


def test_inspect_marks_the_source_host_and_the_targets_the_export_never_saw(export_dir, capsys, monkeypatch):
    monkeypatch.delenv("N8N_SOURCE_URL", raising=False)
    args = argparse.Namespace(directory=str(export_dir), source_host=None)
    assert migrate.cmd_inspect(args) == 0
    out = capsys.readouterr().out
    assert f"{SOURCE}  3 occurrence(s) in 2 node(s)  <-- MOVES" in out
    assert "api.airtable.com  1 occurrence(s) in 1 node(s)\n" in out
    assert "Sticky notes only" in out
    assert f"{SOURCE}: --rewrite-host would replace 3 occurrence(s) in nodes plus 1 in sticky notes." in out
    assert "wfZ  <-- NOT IN THIS EXPORT" in out
    assert "wfB\n      called by Organ A / Run B" in out
    assert "wfE  <-- NOT IN THIS EXPORT  named by 1: Organ A" in out
    assert "Devon Capture Key  (cred1)  httpHeaderAuth" in out


def test_inspect_source_host_flag_overrides_the_n8n_cloud_guess(export_dir, capsys):
    args = argparse.Namespace(directory=str(export_dir), source_host="api.airtable.com")
    migrate.cmd_inspect(args)
    out = capsys.readouterr().out
    assert "api.airtable.com  1 occurrence(s) in 1 node(s)  <-- MOVES" in out
    assert f"{SOURCE}  3 occurrence(s) in 2 node(s)\n" in out


# ---------------------------------------------------------------------------
# import with a host rewrite, against a fake target
# ---------------------------------------------------------------------------

class FakeTarget:
    """Just enough of the n8n public API for import and repoint."""

    def __init__(self, existing=None, fail_on_post=None, refuse_settings=()):
        self.workflows = {w["id"]: w for w in (existing or [])}
        self.calls = []
        self.counter = 0
        self.fail_on_post = fail_on_post      # the Nth POST raises, like a network drop
        self.refuse_settings = set(refuse_settings)  # settings keys the API schema rejects

    def request(self, base, key, path, method="GET", payload=None):
        self.calls.append((method, path, payload))
        if method == "GET" and path.startswith("/api/v1/workflows?"):
            return {"data": [{"id": i, "name": w["name"]} for i, w in self.workflows.items()], "nextCursor": None}
        if method == "GET" and path.startswith("/api/v1/workflows/"):
            return json.loads(json.dumps(self.workflows[path.rsplit("/", 1)[1]]))
        if method == "POST" and path == "/api/v1/workflows":
            posts = sum(1 for c in self.calls if c[0] == "POST")
            if self.fail_on_post == posts:
                raise migrate.ApiError("POST /api/v1/workflows could not reach the target: connection reset")
            refused = sorted(self.refuse_settings & set((payload or {}).get("settings") or {}))
            if refused:
                raise migrate.ApiError(f"POST /api/v1/workflows returned HTTP 400: request/body/settings/{refused[0]} must NOT have additional properties")
            self.counter += 1
            new_id = f"new{self.counter}"
            self.workflows[new_id] = {"id": new_id, **payload}
            return {"id": new_id}
        if method == "PUT" and path.startswith("/api/v1/workflows/"):
            wf_id = path.rsplit("/", 1)[1]
            self.workflows[wf_id] = {"id": wf_id, **payload}
            return {"id": wf_id}
        raise AssertionError(f"unexpected call {method} {path}")


@pytest.fixture
def target(monkeypatch):
    fake = FakeTarget()
    monkeypatch.setattr(migrate, "_request", fake.request)
    monkeypatch.setenv("N8N_TARGET_URL", f"https://{TARGET}")
    monkeypatch.setenv("N8N_TARGET_KEY", "k")
    return fake


def _import_args(directory, **overrides):
    base = {"directory": str(directory), "confirm": False, "allow_existing": False, "rewrite_host": None}
    base.update(overrides)
    return argparse.Namespace(**base)


def test_import_dry_run_prints_the_rewrite_plan_and_creates_nothing(export_dir, target, capsys):
    assert migrate.cmd_import(_import_args(export_dir, rewrite_host=[f"{SOURCE}={TARGET}"])) == 0
    out = capsys.readouterr().out
    assert "Host rewrite plan, 3 occurrence(s) in nodes plus 1 in sticky notes, across 1 workflow(s):" in out
    assert "Organ A / Call B  x1" in out
    assert "Organ A / Decide  x2" in out
    assert "Organ A / Sticky  x1  (sticky note)" in out
    assert "Would create 3 workflow(s)" in out
    assert not [c for c in target.calls if c[0] == "POST"]
    assert not (export_dir / "_id_map.json").exists()


def test_import_rewrites_the_host_in_what_it_posts_and_records_it_in_the_id_map(export_dir, target):
    assert migrate.cmd_import(_import_args(export_dir, confirm=True, rewrite_host=[f"{SOURCE}={TARGET}"])) == 0
    posted = [c[2] for c in target.calls if c[0] == "POST"]
    assert len(posted) == 3
    assert all(SOURCE not in json.dumps(p) for p in posted)
    organ_a = next(p for p in posted if p["name"] == "Organ A")
    decide = next(n for n in organ_a["nodes"] if n["name"] == "Decide")
    assert decide["parameters"]["jsCode"].count(TARGET) == 2
    assert "api.airtable.com" in decide["parameters"]["jsCode"], "other hosts are untouched"
    assert set(organ_a) == set(migrate.CREATE_FIELDS), "only the create fields are sent"
    assert "active" not in organ_a
    id_map = json.loads((export_dir / "_id_map.json").read_text(encoding="utf-8"))
    assert id_map["wfA"]["host_rewrites"] == [
        {"node": "Call B", "occurrences": 1, "sticky_note": False},
        {"node": "Decide", "occurrences": 2, "sticky_note": False},
        {"node": "Sticky", "occurrences": 1, "sticky_note": True},
    ]
    assert id_map["wfA"]["read_back"] == "ok"
    assert id_map["wfA"]["was_active_on_source"] is True
    assert id_map["wfC"]["host_rewrites"] == []
    # The export on disk is untouched, so the rewrite is reversible by re-import.
    on_disk = json.loads((export_dir / migrate._slug("Organ A", "wfA")).read_text(encoding="utf-8"))
    assert SOURCE in json.dumps(on_disk)


def test_import_without_a_rewrite_posts_the_source_host_verbatim(export_dir, target):
    migrate.cmd_import(_import_args(export_dir, confirm=True))
    posted = [c[2] for c in target.calls if c[0] == "POST"]
    assert any(SOURCE in json.dumps(p) for p in posted)


def test_import_refuses_a_path_collision_before_asking_about_the_populated_target(export_dir, monkeypatch, capsys):
    fake = FakeTarget(existing=[{
        "id": "live1", "name": "Live Door",
        "nodes": [{"name": "Door", "type": "n8n-nodes-base.webhook", "parameters": {"path": "devon-a"}}],
    }])
    monkeypatch.setattr(migrate, "_request", fake.request)
    monkeypatch.setenv("N8N_TARGET_URL", f"https://{TARGET}")
    monkeypatch.setenv("N8N_TARGET_KEY", "k")
    assert migrate.cmd_import(_import_args(export_dir, confirm=True)) == 2
    out = capsys.readouterr().out
    assert "webhook path /devon-a  (held by Live Door" in out
    assert migrate.cmd_import(_import_args(export_dir, confirm=True, allow_existing=True)) == 2, "the flag does not override a collision"
    assert not [c for c in fake.calls if c[0] == "POST"]


def test_import_refuses_a_name_already_on_the_target_as_a_lost_map(export_dir, monkeypatch, capsys):
    fake = FakeTarget(existing=[{"id": "live9", "name": "Organ B", "nodes": [], "connections": {}, "settings": {}}])
    monkeypatch.setattr(migrate, "_request", fake.request)
    monkeypatch.setenv("N8N_TARGET_URL", f"https://{TARGET}")
    monkeypatch.setenv("N8N_TARGET_KEY", "k")
    assert migrate.cmd_import(_import_args(export_dir, confirm=True, allow_existing=True)) == 2
    out = capsys.readouterr().out
    assert "workflow named 'Organ B'  (target id live9" in out
    assert not [c for c in fake.calls if c[0] == "POST"]


def test_import_needs_the_flag_for_an_unrelated_populated_target(export_dir, monkeypatch, capsys):
    fake = FakeTarget(existing=[{"id": "other", "name": "Unrelated", "nodes": [], "connections": {}, "settings": {}}])
    monkeypatch.setattr(migrate, "_request", fake.request)
    monkeypatch.setenv("N8N_TARGET_URL", f"https://{TARGET}")
    monkeypatch.setenv("N8N_TARGET_KEY", "k")
    with pytest.raises(SystemExit, match="none of them colliding"):
        migrate.cmd_import(_import_args(export_dir, confirm=True))
    assert migrate.cmd_import(_import_args(export_dir, confirm=True, allow_existing=True)) == 0
    assert len([c for c in fake.calls if c[0] == "POST"]) == 3


def test_import_reads_back_what_it_created_and_reports_a_silent_drop(export_dir, monkeypatch, capsys):
    class Dropping(FakeTarget):
        def request(self, base, key, path, method="GET", payload=None):
            if method == "POST":
                payload = json.loads(json.dumps(payload))
                for node in payload["nodes"]:
                    node.pop("webhookId", None)
                payload["settings"].pop("errorWorkflow", None)
            return super().request(base, key, path, method, payload)
    fake = Dropping()
    monkeypatch.setattr(migrate, "_request", fake.request)
    monkeypatch.setenv("N8N_TARGET_URL", f"https://{TARGET}")
    monkeypatch.setenv("N8N_TARGET_KEY", "k")
    data = _workflow_a()
    data["nodes"][0]["webhookId"] = "hook-1"
    (export_dir / migrate._slug(data["name"], data["id"])).write_text(json.dumps(data), encoding="utf-8")
    assert migrate.cmd_import(_import_args(export_dir, confirm=True)) == 2
    out = capsys.readouterr().out
    assert "READ BACK DIFFERS: webhook ids differ: sent ['hook-1'], stored []" in out
    assert "READ BACK DIFFERS: settings.errorWorkflow sent 'wfE', stored None" in out
    id_map = json.loads((export_dir / "_id_map.json").read_text(encoding="utf-8"))
    assert len(id_map["wfA"]["read_back"]) == 2 and id_map["wfB"]["read_back"] == "ok"


def test_import_refuses_to_create_the_estate_on_the_instance_it_came_from(export_dir, target):
    (export_dir / "_export_meta.json").write_text(json.dumps({"source_url": f"https://{TARGET}", "source_host": TARGET}), encoding="utf-8")
    with pytest.raises(SystemExit) as caught:
        migrate.cmd_import(_import_args(export_dir, confirm=True))
    assert "where this export came from" in str(caught.value)
    assert not [c for c in target.calls if c[0] == "POST"]


def test_import_twice_creates_nothing_the_second_time(export_dir, target, capsys):
    assert migrate.cmd_import(_import_args(export_dir, confirm=True)) == 0
    first = [c for c in target.calls if c[0] == "POST"]
    assert len(first) == 3
    # The target is populated now, so the second run has to say --allow-existing.
    assert migrate.cmd_import(_import_args(export_dir, confirm=True, allow_existing=True)) == 0
    out = capsys.readouterr().out
    assert len([c for c in target.calls if c[0] == "POST"]) == 3, "no duplicate created"
    assert "Created 0 workflow(s), all INACTIVE, skipped 3 already in the map" in out
    assert "skipped  Organ A  already created as" in out


def test_import_keeps_the_map_of_what_it_made_when_a_post_dies(export_dir, monkeypatch, capsys):
    fake = FakeTarget(fail_on_post=2)
    monkeypatch.setattr(migrate, "_request", fake.request)
    monkeypatch.setenv("N8N_TARGET_URL", f"https://{TARGET}")
    monkeypatch.setenv("N8N_TARGET_KEY", "k")
    with pytest.raises(migrate.ApiError):
        migrate.cmd_import(_import_args(export_dir, confirm=True))
    out = capsys.readouterr().out
    assert "Stopped at" in out and "1 created before it" in out
    id_map = json.loads((export_dir / "_id_map.json").read_text(encoding="utf-8"))
    assert list(id_map) == ["wfA"] and id_map["wfA"]["new_id"] == "new1"
    # The re-run skips the one that exists and creates the other two, once each.
    fake.fail_on_post = None
    assert migrate.cmd_import(_import_args(export_dir, confirm=True, allow_existing=True)) == 0
    id_map = json.loads((export_dir / "_id_map.json").read_text(encoding="utf-8"))
    assert {k: v["new_id"] for k, v in id_map.items()} == {"wfA": "new1", "wfB": "new2", "wfC": "new3"}
    assert len(fake.workflows) == 3


def test_import_drops_only_the_settings_keys_the_target_refuses_and_says_so(export_dir, monkeypatch, capsys):
    data = _workflow_a()
    data["settings"] = {"executionOrder": "v1", "errorWorkflow": "wfE", "callerPolicy": "workflowsFromSameOwner", "availableInMCP": True}
    (export_dir / migrate._slug(data["name"], data["id"])).write_text(json.dumps(data), encoding="utf-8")
    fake = FakeTarget(refuse_settings={"callerPolicy", "availableInMCP"})
    monkeypatch.setattr(migrate, "_request", fake.request)
    monkeypatch.setenv("N8N_TARGET_URL", f"https://{TARGET}")
    monkeypatch.setenv("N8N_TARGET_KEY", "k")
    assert migrate.cmd_import(_import_args(export_dir, confirm=True)) == 0
    out = capsys.readouterr().out
    organ_a = next(w for w in fake.workflows.values() if w["name"] == "Organ A")
    assert organ_a["settings"] == {"executionOrder": "v1", "errorWorkflow": "wfE"}
    assert "dropped settings.availableInMCP" in out and "dropped settings.callerPolicy" in out
    id_map = json.loads((export_dir / "_id_map.json").read_text(encoding="utf-8"))
    assert sorted(id_map["wfA"]["dropped_settings"]) == ["availableInMCP", "callerPolicy"]
    assert id_map["wfB"]["dropped_settings"] == []


def test_create_workflow_gives_up_on_a_400_that_names_no_settings_key(monkeypatch):
    def refuse(base, key, path, method="GET", payload=None):
        raise migrate.ApiError("POST /api/v1/workflows returned HTTP 400: request/body/nodes/0/type must be string")
    monkeypatch.setattr(migrate, "_request", refuse)
    with pytest.raises(migrate.ApiError, match="nodes/0/type"):
        migrate._create_workflow("https://x", "k", {"name": "n", "nodes": [], "connections": {}, "settings": {"a": 1}})


# ---------------------------------------------------------------------------
# repoint
# ---------------------------------------------------------------------------

def test_repoint_workflow_rewrites_every_mapped_reference_and_names_the_rest():
    workflow = _workflow_a()
    ids = {"wfA": "new1", "wfB": "new2"}
    names = {"wfA": "Organ A", "wfB": "Organ B"}
    creds = {"cred1": {"id": "c-new", "name": "Devon Capture Key (VPS)"}}
    tables = {}
    out, changed, dangling, done = migrate._repoint_workflow(workflow, ids, names, creds, tables)
    assert done == []

    run_b = next(n for n in out["nodes"] if n["name"] == "Run B")
    assert run_b["parameters"]["workflowId"] == {"__rl": True, "mode": "list", "value": "new2", "cachedResultName": "Organ B"}
    door = next(n for n in out["nodes"] if n["name"] == "Door")
    assert door["credentials"]["httpHeaderAuth"] == {"id": "c-new", "name": "Devon Capture Key (VPS)"}
    assert "Run B: Execute Workflow wfB -> new2" in changed
    assert "Door: credential httpHeaderAuth cred1 -> c-new" in changed
    assert "Call B: credential httpHeaderAuth cred1 -> c-new" in changed
    assert dangling == [
        "Ledger Row: data table tbl1 has no entry in the table map",
        "settings: errorWorkflow wfE is not in the id map",
    ]
    # The input is never mutated.
    assert workflow["nodes"][0]["credentials"]["httpHeaderAuth"]["id"] == "cred1"
    assert workflow["settings"]["errorWorkflow"] == "wfE"


def test_repoint_workflow_reports_an_expression_target_for_a_human():
    workflow = {"nodes": [{"name": "Dyn", "type": "n8n-nodes-base.executeWorkflow",
                           "parameters": {"workflowId": {"__rl": True, "mode": "list"}}}], "settings": {}}
    _, changed, dangling, _ = migrate._repoint_workflow(workflow, {}, {}, {}, {})
    assert changed == []
    assert dangling == ["Dyn: Execute Workflow target is set by expression or name; check it by hand"]


def test_repoint_workflow_is_idempotent_and_tolerates_null_settings_and_table_by_name_node():
    workflow = {
        "settings": None,
        "nodes": [
            {"name": "Run B", "type": "n8n-nodes-base.executeWorkflow", "parameters": {"workflowId": "new2"}},
            {"name": "Door", "type": "n8n-nodes-base.webhook", "parameters": {}, "credentials": {"httpHeaderAuth": {"id": "c-new", "name": "k"}}},
            {"name": "Old Style", "type": "n8n-nodes-base.dataTable", "parameters": {"table": "tbl1"}},
            {"name": "Loose", "type": "n8n-nodes-base.emailSend", "parameters": {}, "credentials": {"smtp": {"name": "no id here"}}},
        ],
    }
    ids = {"wfB": "new2"}
    creds = {"cred1": {"id": "c-new", "name": None}}
    tables = {"tbl1": {"id": "t1", "name": None}}
    out, changed, dangling, done = migrate._repoint_workflow(workflow, ids, {}, creds, tables)
    assert changed == ["Old Style: data table tbl1 -> t1"]
    assert done == ["Run B: Execute Workflow already at new2", "Door: credential httpHeaderAuth already at c-new"]
    assert dangling == ["Loose: credential smtp is bound with no id; bind it by hand"]
    assert out["settings"] == {}
    # A second pass over the result changes nothing and dangles the same one line.
    out2, changed2, dangling2, done2 = migrate._repoint_workflow(out, ids, {}, creds, tables)
    assert changed2 == [] and dangling2 == dangling and "Old Style: data table already at t1" in done2


def test_repoint_end_to_end_writes_only_with_confirm_and_returns_2_while_anything_dangles(export_dir, target, capsys, tmp_path):
    migrate.cmd_import(_import_args(export_dir, confirm=True))
    capsys.readouterr()
    cred_map = tmp_path / "creds.json"
    cred_map.write_text(json.dumps({"cred1": "c1", "cred2": "c2", "cred3": "c3"}), encoding="utf-8")
    table_map = tmp_path / "tables.json"
    table_map.write_text(json.dumps({"tbl1": {"id": "t1", "name": "ledger"}, "tbl2": "t2"}), encoding="utf-8")

    dry = argparse.Namespace(directory=str(export_dir), credential_map=str(cred_map), table_map=str(table_map), confirm=False)
    assert migrate.cmd_repoint(dry) == 2
    out = capsys.readouterr().out
    assert "3 workflow(s) would be written back. Nothing was written" in out
    assert "STILL AT THE SOURCE: settings: errorWorkflow wfE is not in the id map" in out
    assert "STILL AT THE SOURCE: Run Z: Execute Workflow target wfZ is not in the id map" in out
    assert not [c for c in target.calls if c[0] == "PUT"]

    wet = argparse.Namespace(directory=str(export_dir), credential_map=str(cred_map), table_map=str(table_map), confirm=True)
    assert migrate.cmd_repoint(wet) == 2
    puts = [c for c in target.calls if c[0] == "PUT"]
    assert len(puts) == 3, "every workflow with at least one mapped reference is written, Organ B for its SMTP credential"
    stored_a = target.workflows["new1"]
    run_b = next(n for n in stored_a["nodes"] if n["name"] == "Run B")
    assert run_b["parameters"]["workflowId"]["value"] == "new2"
    ledger = next(n for n in stored_a["nodes"] if n["name"] == "Ledger Row")
    assert ledger["parameters"]["dataTableId"]["value"] == "t1"
    assert stored_a["settings"]["errorWorkflow"] == "wfE", "an unmapped error workflow is left for a human, not blanked"
    assert "active" not in stored_a
    assert set(stored_a) == {"id", *migrate.CREATE_FIELDS}


def test_repoint_returns_0_once_every_reference_is_mapped(export_dir, target, capsys, tmp_path):
    migrate.cmd_import(_import_args(export_dir, confirm=True))
    id_map = json.loads((export_dir / "_id_map.json").read_text(encoding="utf-8"))
    # Pretend the error workflow and the orphan's target were imported too.
    id_map["wfE"] = {"name": "Error Alarm", "new_id": "newE", "was_active_on_source": True, "host_rewrites": []}
    id_map["wfZ"] = {"name": "Z", "new_id": "newZ", "was_active_on_source": False, "host_rewrites": []}
    target.workflows["newE"] = {"id": "newE", "name": "Error Alarm", "nodes": [], "connections": {}, "settings": {}}
    target.workflows["newZ"] = {"id": "newZ", "name": "Z", "nodes": [], "connections": {}, "settings": {}}
    (export_dir / "_id_map.json").write_text(json.dumps(id_map), encoding="utf-8")
    cred_map = tmp_path / "creds.json"
    cred_map.write_text(json.dumps({"cred1": "c1", "cred2": "c2", "cred3": "c3"}), encoding="utf-8")
    table_map = tmp_path / "tables.json"
    table_map.write_text(json.dumps({"tbl1": "t1", "tbl2": "t2"}), encoding="utf-8")
    args = argparse.Namespace(directory=str(export_dir), credential_map=str(cred_map), table_map=str(table_map), confirm=True)
    assert migrate.cmd_repoint(args) == 0
    assert "Every reference the tool understands now points at the target." in capsys.readouterr().out
    assert target.workflows["new1"]["settings"]["errorWorkflow"] == "newE"
    puts_before = len([c for c in target.calls if c[0] == "PUT"])
    # Second run: nothing to write, everything reported as already done, still exit 0.
    assert migrate.cmd_repoint(args) == 0
    out = capsys.readouterr().out
    assert len([c for c in target.calls if c[0] == "PUT"]) == puts_before
    assert "already done: Run B: Execute Workflow already at new2" in out
    assert "STILL AT THE SOURCE" not in out


def test_repoint_names_the_map_entries_that_import_never_created(export_dir, target, capsys):
    migrate.cmd_import(_import_args(export_dir, confirm=True))
    id_map = json.loads((export_dir / "_id_map.json").read_text(encoding="utf-8"))
    id_map["wfC"]["new_id"] = ""
    (export_dir / "_id_map.json").write_text(json.dumps(id_map), encoding="utf-8")
    capsys.readouterr()
    migrate.cmd_repoint(argparse.Namespace(directory=str(export_dir), credential_map=None, table_map=None, confirm=False))
    out = capsys.readouterr().out
    assert "NOT ON THE TARGET: Orphan Caller (wfC) has no new id in the map" in out


def test_export_meta_names_the_source_host(monkeypatch, tmp_path):
    fake = FakeTarget(existing=[{"id": "s1", "name": "One", "nodes": [], "connections": {}, "settings": {}, "active": True}])
    monkeypatch.setattr(migrate, "_request", fake.request)
    monkeypatch.setenv("N8N_SOURCE_URL", "https://source.app.n8n.cloud/")
    monkeypatch.setenv("N8N_SOURCE_KEY", "k")
    assert migrate.cmd_export(argparse.Namespace(directory=str(tmp_path))) == 0
    meta = json.loads((tmp_path / "_export_meta.json").read_text(encoding="utf-8"))
    assert meta["source_host"] == "source.app.n8n.cloud"
    assert (tmp_path / "_index.json").exists()
    assert (tmp_path / migrate._slug("One", "s1")).exists()


def test_repoint_needs_the_id_map(tmp_path, target):
    with pytest.raises(SystemExit):
        migrate.cmd_repoint(argparse.Namespace(directory=str(tmp_path), credential_map=None, table_map=None, confirm=False))


def test_no_banned_dashes_in_the_tool_or_this_file():
    banned = (chr(0x2014), chr(0x2013))
    here = pathlib.Path(__file__).resolve().parent
    for path in (here / "scripts" / "n8n_migrate.py", pathlib.Path(__file__)):
        text = path.read_text(encoding="utf-8")
        assert not any(ch in text for ch in banned), path

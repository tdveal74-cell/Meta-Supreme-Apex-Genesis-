#!/usr/bin/env python3
"""Move an n8n estate between instances, without the silent failures.

Four subcommands, meant to be run in order:

    export    pull every workflow from the source instance to a directory
    inspect   report what the exported set needs that does NOT travel with it
    import    create the workflows on the target, always inactive
    repoint   rewrite sub-workflow, error workflow, credential and data table
              references on the target from id maps, and list whatever is
              still pointing at the source

Credentials are read from the environment and never written to disk:

    N8N_SOURCE_URL   https://your-instance.app.n8n.cloud
    N8N_SOURCE_KEY   an API key on the source, needs workflow:list and :read
    N8N_TARGET_URL   https://n8n.your-host
    N8N_TARGET_KEY   an API key on the target, needs workflow:create, and
                     workflow:read plus workflow:update for repoint

Why this exists rather than a shell one-liner. Six things do not move with a
workflow, and most of them fail silently rather than loudly:

  * Credentials are referenced by id. A fresh instance mints new ids, so every
    reference dangles until it is re-linked. `inspect` lists them with their
    types; `repoint --credential-map` rewrites them.
  * n8n data tables do not export with workflows at all. `inspect` names the
    ones your workflows read and write so you can rebuild them first;
    `repoint --table-map` rewrites the node references.
  * Webhook URLs carry the host. Everything that POSTs to them keeps posting
    at the old one until it is repointed.
  * The source host is also written INSIDE workflows: Code nodes build organ
    to organ URLs from a HOST constant, HTTP Request nodes carry absolute
    URLs, and both keep calling the source after import. `inspect` lists
    every occurrence by node, and `import --rewrite-host OLD=NEW` replaces
    the literal, printing each node it touched.
  * Execute Workflow nodes and the errorWorkflow setting address other
    workflows by id, and the target mints new ids. `inspect` lists them and
    says which are not in the export; `repoint` rewrites them from the id map
    that `import` writes.
  * A webhook path collision does not error. n8n routes to whichever workflow
    was published first, so importing onto a non-empty instance can silently
    hijack a live path. `import` refuses when it detects one.

Nothing here activates a workflow. Two live instances polling the same lanes
is the failure this tool is most concerned with avoiding; activation stays a
deliberate human step after the target has been checked.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

TIMEOUT = 60

# n8n's create endpoint rejects the fields it owns. Everything not in this set
# is dropped on import: id, active, tags, createdAt, updatedAt, versionId,
# meta, pinData, shared, triggerCount and anything else the API adds later.
CREATE_FIELDS = ("name", "nodes", "connections", "settings")

# Any absolute URL host inside a parameter value, expression or Code body.
HOST_RE = re.compile(r"https?://([A-Za-z0-9.-]+)")

# The parameter fields that address an n8n data table by id. `table` on its
# own is an Airtable table name on Airtable nodes, so it only counts on a
# node whose type says data table.
TABLE_ID_FIELDS = ("dataTableId", "tableId")


class ApiError(RuntimeError):
    pass


def _request(base: str, key: str, path: str, method: str = "GET",
             payload: Optional[Dict[str, Any]] = None) -> Any:
    url = f"{base.rstrip('/')}{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("X-N8N-API-KEY", key)
    req.add_header("Accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            body = response.read().decode()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:400]
        raise ApiError(f"{method} {path} returned HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise ApiError(f"{method} {path} could not reach {base}: {exc.reason}") from exc
    return json.loads(body) if body else {}


def _paged_workflows(base: str, key: str) -> Iterator[Dict[str, Any]]:
    """Walk every page. n8n returns {data: [...], nextCursor: str|None}."""
    cursor = None
    while True:
        query = "?limit=100" + (f"&cursor={urllib.parse.quote(cursor)}" if cursor else "")
        page = _request(base, key, f"/api/v1/workflows{query}")
        for workflow in page.get("data", []):
            yield workflow
        cursor = page.get("nextCursor")
        if not cursor:
            return


def _slug(name: str, workflow_id: str) -> str:
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in name).strip("-")
    return f"{safe[:70] or 'workflow'}__{workflow_id}.json"


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        sys.exit(f"{name} is not set. See the header of this file.")
    return value


def _exports(directory: pathlib.Path) -> Iterator[Tuple[pathlib.Path, Dict[str, Any]]]:
    for path in sorted(directory.glob("*.json")):
        if path.name.startswith("_"):
            continue
        yield path, json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# small pure helpers, tested on their own
# ---------------------------------------------------------------------------

def _strings(value: Any, path: str = "") -> Iterator[Tuple[str, str]]:
    """Yield (path, text) for every string leaf in a JSON value."""
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, inner in value.items():
            yield from _strings(inner, f"{path}.{key}" if path else str(key))
    elif isinstance(value, list):
        for index, inner in enumerate(value):
            yield from _strings(inner, f"{path}[{index}]")


def _rewrite_strings(value: Any, pairs: Sequence[Tuple[str, str]]) -> Tuple[Any, int]:
    """Copy of value with every literal OLD replaced by NEW, and how many were replaced.

    Pairs apply in order. Numbers, booleans and nulls are never touched, so a
    rewrite cannot change anything but the literal it was given.
    """
    if isinstance(value, str):
        count = 0
        for old, new in pairs:
            hits = value.count(old)
            if hits:
                value = value.replace(old, new)
                count += hits
        return value, count
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        total = 0
        for key, inner in value.items():
            out[key], hits = _rewrite_strings(inner, pairs)
            total += hits
        return out, total
    if isinstance(value, list):
        items: List[Any] = []
        total = 0
        for inner in value:
            rewritten, hits = _rewrite_strings(inner, pairs)
            items.append(rewritten)
            total += hits
        return items, total
    return value, 0


def _ref_id(value: Any) -> str:
    """The id inside an n8n resource reference: a bare string or {__rl, mode, value}."""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        inner = value.get("value")
        return str(inner).strip() if isinstance(inner, (str, int)) else ""
    return ""


def _set_ref_id(value: Any, new_id: str, new_name: Optional[str]) -> Any:
    if isinstance(value, dict):
        out = dict(value)
        out["value"] = new_id
        if new_name and "cachedResultName" in out:
            out["cachedResultName"] = new_name
        return out
    return new_id


def _is_sub_workflow_node(node_type: str) -> bool:
    lowered = node_type.lower()
    if lowered.endswith("trigger"):
        return False
    return "executeworkflow" in lowered or "toolworkflow" in lowered


def _is_data_table_node(node_type: str) -> bool:
    return "datatable" in node_type.lower()


def _parse_pairs(raw: Optional[List[str]]) -> List[Tuple[str, str]]:
    pairs: List[Tuple[str, str]] = []
    for item in raw or []:
        if "=" not in item:
            sys.exit(f"--rewrite-host wants OLD=NEW, got {item!r}")
        old, new = item.split("=", 1)
        if not old or not new:
            sys.exit(f"--rewrite-host wants OLD=NEW with both sides present, got {item!r}")
        pairs.append((old, new))
    return pairs


def _load_map(path: Optional[str]) -> Dict[str, Dict[str, Optional[str]]]:
    """A JSON map of {old_id: new_id} or {old_id: {id, name}}, normalised."""
    if not path:
        return {}
    raw = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        sys.exit(f"{path} must hold a JSON object keyed by the source id")
    out: Dict[str, Dict[str, Optional[str]]] = {}
    for old, new in raw.items():
        if isinstance(new, str):
            out[str(old)] = {"id": new, "name": None}
        elif isinstance(new, dict) and new.get("id"):
            out[str(old)] = {"id": str(new["id"]), "name": new.get("name")}
        else:
            sys.exit(f"{path}: entry {old!r} must be a new id or an object with id")
    return out


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------

def cmd_export(args: argparse.Namespace) -> int:
    base, key = _env("N8N_SOURCE_URL"), _env("N8N_SOURCE_KEY")
    out = pathlib.Path(args.directory)
    out.mkdir(parents=True, exist_ok=True)

    written = 0
    index: List[Dict[str, Any]] = []
    for preview in _paged_workflows(base, key):
        workflow_id = preview["id"]
        # The list endpoint returns a preview; the nodes only come from the
        # single-workflow read, so fetch each one rather than trusting the page.
        full = _request(base, key, f"/api/v1/workflows/{workflow_id}")
        path = out / _slug(full.get("name", "workflow"), workflow_id)
        path.write_text(json.dumps(full, indent=2, sort_keys=True), encoding="utf-8")
        index.append({
            "id": workflow_id,
            "name": full.get("name"),
            "active": full.get("active", False),
            "file": path.name,
        })
        written += 1
        print(f"  {full.get('name')}  ({workflow_id})")

    (out / "_index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    print(f"\nExported {written} workflow(s) to {out}/")
    print(f"{sum(1 for w in index if w['active'])} of them are active on the source.")
    return 0


# ---------------------------------------------------------------------------
# inspect
# ---------------------------------------------------------------------------

class Scan:
    """Everything an export references that does not travel with it."""

    def __init__(self) -> None:
        self.workflows: List[Dict[str, Any]] = []
        self.ids: set = set()
        self.credentials: Dict[str, Dict[str, Any]] = {}     # id -> {name, types}
        self.webhooks: Dict[str, List[str]] = {}              # path -> [workflow names]
        self.tables: Dict[str, List[str]] = {}                # table id -> [workflow names]
        self.hosts: Dict[str, List[Tuple[str, str, int]]] = {}         # host -> [(wf, node, n)]
        self.sticky_hosts: Dict[str, List[Tuple[str, str, int]]] = {}  # same, sticky notes
        self.sub_targets: Dict[str, List[Tuple[str, str]]] = {}        # target id -> [(wf, node)]
        self.error_workflows: Dict[str, List[str]] = {}       # error workflow id -> [wf names]


def _scan(directory: pathlib.Path) -> Scan:
    scan = Scan()
    for path, data in _exports(directory):
        name = data.get("name", path.stem)
        scan.workflows.append({"name": name, "id": data.get("id"), "active": data.get("active", False)})
        if data.get("id"):
            scan.ids.add(str(data["id"]))

        error_workflow = (data.get("settings") or {}).get("errorWorkflow")
        if error_workflow:
            scan.error_workflows.setdefault(str(error_workflow), []).append(name)

        for node in data.get("nodes", []):
            node_name = str(node.get("name", "(unnamed node)"))
            node_type = str(node.get("type", ""))
            params = node.get("parameters") or {}

            for cred_type, cred in (node.get("credentials") or {}).items():
                if isinstance(cred, dict) and cred.get("id"):
                    entry = scan.credentials.setdefault(
                        str(cred["id"]), {"name": cred.get("name", "(unnamed)"), "types": set()})
                    entry["types"].add(str(cred_type))

            if "webhook" in node_type.lower() or node_type.lower().endswith("chattrigger"):
                webhook_path = params.get("path")
                if webhook_path:
                    scan.webhooks.setdefault(str(webhook_path), []).append(name)

            # Data table nodes reference the table by id, and some workflows
            # reach them over HTTP. Catch both shapes without guessing hard.
            table_fields = TABLE_ID_FIELDS + (("table",) if _is_data_table_node(node_type) else ())
            for field in table_fields:
                ref = _ref_id(params.get(field))
                if ref:
                    scan.tables.setdefault(ref, []).append(name)

            if _is_sub_workflow_node(node_type):
                ref = _ref_id(params.get("workflowId")) or "(no id: set by expression or by name)"
                scan.sub_targets.setdefault(ref, []).append((name, node_name))

            per_node: Dict[str, int] = {}
            for _, text in _strings(params):
                for host in HOST_RE.findall(text):
                    per_node[host] = per_node.get(host, 0) + 1
            bucket = scan.sticky_hosts if node_type.lower().endswith("stickynote") else scan.hosts
            for host, hits in sorted(per_node.items()):
                bucket.setdefault(host, []).append((name, node_name, hits))

    return scan


def _source_host(explicit: Optional[str]) -> Optional[str]:
    if explicit:
        return explicit.strip().lower()
    url = os.environ.get("N8N_SOURCE_URL", "").strip()
    return urllib.parse.urlparse(url).hostname if url else None


def _host_moves(host: str, source_host: Optional[str]) -> bool:
    lowered = host.lower()
    if source_host:
        return lowered == source_host
    return "n8n.cloud" in lowered


def cmd_inspect(args: argparse.Namespace) -> int:
    directory = pathlib.Path(args.directory)
    if not directory.is_dir():
        sys.exit(f"{directory} is not a directory. Run export first.")

    scan = _scan(directory)
    active = [w for w in scan.workflows if w["active"]]
    source_host = _source_host(getattr(args, "source_host", None))

    print(f"{len(scan.workflows)} workflow(s), {len(active)} active on the source.\n")

    print("CREDENTIALS referenced by id, with the credential type each node expects.")
    print("A fresh target mints new ids, so each of these must exist on the target")
    print("and be re-linked (repoint --credential-map does the re-linking):")
    for cred_id, entry in sorted(scan.credentials.items(), key=lambda kv: str(kv[1]["name"]).lower()):
        print(f"  {entry['name']}  ({cred_id})  {', '.join(sorted(entry['types']))}")
    if not scan.credentials:
        print("  (none found)")

    print("\nWEBHOOK PATHS. Every one of these changes host on the target, and")
    print("anything posting to the old host keeps posting there until repointed:")
    for path, owners in sorted(scan.webhooks.items()):
        collision = "  <-- SHARED BY MORE THAN ONE WORKFLOW" if len(owners) > 1 else ""
        print(f"  /{path}  ({', '.join(sorted(set(owners)))}){collision}")
    if not scan.webhooks:
        print("  (none found)")

    print("\nDATA TABLES referenced. These do NOT export with workflows and must")
    print("be recreated on the target before anything that reads them runs:")
    for table, owners in sorted(scan.tables.items()):
        print(f"  {table}  ({', '.join(sorted(set(owners)))})")
    if not scan.tables:
        print("  (none detected; check by hand, node shapes vary by n8n version)")

    print("\nHOSTS written inside workflows (HTTP Request urls, Code bodies, expressions),")
    print("sticky notes excluded. A host marked MOVES is the source instance itself:")
    print("every occurrence keeps calling the source after import unless it is")
    print("rewritten (import --rewrite-host OLD=NEW):")
    moving = 0
    for host, refs in sorted(scan.hosts.items()):
        total = sum(n for _, _, n in refs)
        mark = "  <-- MOVES" if _host_moves(host, source_host) else ""
        if mark:
            moving += total
        print(f"  {host}  {total} occurrence(s) in {len(refs)} node(s){mark}")
        for workflow, node, hits in refs:
            print(f"      {workflow} / {node}  x{hits}")
    if not scan.hosts:
        print("  (none found)")
    if scan.sticky_hosts:
        print("  Sticky notes only, documentation not behaviour:")
        for host, refs in sorted(scan.sticky_hosts.items()):
            print(f"    {host}  in {', '.join(sorted(set(w for w, _, _ in refs)))}")
    print(f"  {moving} occurrence(s) would be rewritten by --rewrite-host for the source host.")

    print("\nSUB-WORKFLOW TARGETS (Execute Workflow nodes). Ids do not survive import;")
    print("repoint rewrites them from _id_map.json. A target NOT IN THIS EXPORT is")
    print("a workflow the export never saw, and the call will fail on the target:")
    for target, callers in sorted(scan.sub_targets.items()):
        missing = "" if target in scan.ids else "  <-- NOT IN THIS EXPORT"
        print(f"  {target}{missing}")
        for workflow, node in callers:
            print(f"      called by {workflow} / {node}")
    if not scan.sub_targets:
        print("  (none found)")

    print("\nERROR WORKFLOW SETTINGS. A workflow naming an error workflow that is not")
    print("on the target routes its crashes nowhere, and nothing reports that:")
    for target, owners in sorted(scan.error_workflows.items()):
        missing = "" if target in scan.ids else "  <-- NOT IN THIS EXPORT"
        print(f"  {target}{missing}  named by {len(owners)}: {', '.join(sorted(owners))}")
    if not scan.error_workflows:
        print("  (none set)")

    print("\nACTIVE on the source, so these are what a cutover has to switch over.")
    print("Nothing is activated by this tool:")
    for workflow in sorted(active, key=lambda w: str(w["name"]).lower()):
        print(f"  {workflow['name']}")
    return 0


# ---------------------------------------------------------------------------
# import
# ---------------------------------------------------------------------------

def cmd_import(args: argparse.Namespace) -> int:
    directory = pathlib.Path(args.directory)
    if not directory.is_dir():
        sys.exit(f"{directory} is not a directory. Run export first.")
    base, key = _env("N8N_TARGET_URL"), _env("N8N_TARGET_KEY")
    pairs = _parse_pairs(getattr(args, "rewrite_host", None))

    existing = list(_paged_workflows(base, key))
    if existing and not args.allow_existing:
        sys.exit(
            f"The target already has {len(existing)} workflow(s). A webhook path "
            "collision does not error in n8n, it silently routes to whichever "
            "workflow was published first, so importing onto a populated "
            "instance can hijack a live path. Re-run with --allow-existing only "
            "once you have checked for path collisions."
        )

    scan = _scan(directory)
    if existing:
        taken: Dict[str, str] = {}
        for preview in existing:
            full = _request(base, key, f"/api/v1/workflows/{preview['id']}")
            for node in full.get("nodes", []):
                path = (node.get("parameters") or {}).get("path")
                if path and "webhook" in str(node.get("type", "")).lower():
                    taken[str(path)] = full.get("name", preview["id"])
        clashes = sorted(set(scan.webhooks) & set(taken))
        if clashes:
            print("Refusing to import. These webhook paths already exist on the target:")
            for path in clashes:
                print(f"  /{path}  (held by {taken[path]})")
            return 2

    exports = list(_exports(directory))

    # The rewrite plan is printed on the dry run and on the real run alike, per
    # node, so a migrator can read exactly what changed and where.
    plans: Dict[str, List[Dict[str, Any]]] = {}
    if pairs:
        for _, data in exports:
            touched = []
            for node in data.get("nodes", []):
                _, hits = _rewrite_strings(node.get("parameters") or {}, pairs)
                if hits:
                    touched.append({"node": node.get("name", "(unnamed node)"), "occurrences": hits})
            plans[str(data.get("id"))] = touched
        total = sum(t["occurrences"] for touched in plans.values() for t in touched)
        print(f"Host rewrite plan, {total} occurrence(s) across "
              f"{sum(1 for t in plans.values() if t)} workflow(s):")
        for _, data in exports:
            for item in plans.get(str(data.get("id")), []):
                print(f"  {data.get('name')} / {item['node']}  x{item['occurrences']}")

    if not args.confirm:
        print(f"Would create {len(exports)} workflow(s) on {base}, all inactive.")
        print("Re-run with --confirm to actually create them.")
        return 0

    mapping: Dict[str, Dict[str, Any]] = {}
    for _, data in exports:
        payload = {field: data[field] for field in CREATE_FIELDS if field in data}
        payload.setdefault("settings", {})
        if pairs:
            rewritten_nodes = []
            for node in payload.get("nodes", []):
                node = dict(node)
                node["parameters"], _ = _rewrite_strings(node.get("parameters") or {}, pairs)
                rewritten_nodes.append(node)
            payload["nodes"] = rewritten_nodes
        created = _request(base, key, "/api/v1/workflows", method="POST", payload=payload)
        mapping[str(data.get("id"))] = {
            "name": data.get("name", ""),
            "new_id": str(created.get("id", "")),
            "was_active_on_source": bool(data.get("active", False)),
            "host_rewrites": plans.get(str(data.get("id")), []),
        }
        print(f"  created  {data.get('name')}  {data.get('id')} -> {created.get('id')}")

    out = directory / "_id_map.json"
    out.write_text(json.dumps(mapping, indent=2), encoding="utf-8")
    print(f"\nCreated {len(mapping)} workflow(s), all INACTIVE. Id map: {out}")
    print("Next, and in this order:")
    print("  1. Recreate credentials on the target, then write a credential map")
    print("     {old_id: new_id} and run repoint --credential-map to re-link them.")
    print("  2. Recreate the data tables, then a table map, then repoint --table-map.")
    print("  3. repoint --confirm also rewrites Execute Workflow targets and error")
    print("     workflow settings from this id map; read its still-pointing list.")
    print("  4. Smoke one lane end to end while the source is still the live one.")
    print("  5. Deactivate on the source BEFORE activating here. Never both at once.")
    print("  6. Update services/devon/vault.py: N8N_HOST and every webhook entry.")
    return 0


# ---------------------------------------------------------------------------
# repoint
# ---------------------------------------------------------------------------

def _repoint_workflow(workflow: Dict[str, Any],
                      workflow_ids: Dict[str, str],
                      workflow_names: Dict[str, str],
                      cred_map: Dict[str, Dict[str, Optional[str]]],
                      table_map: Dict[str, Dict[str, Optional[str]]],
                      ) -> Tuple[Dict[str, Any], List[str], List[str]]:
    """A repointed copy of one workflow, the changes made, and what still dangles.

    Pure: nothing here talks to an instance. Every reference the maps do not
    cover is reported rather than guessed at, because a reference left at a
    source id fails on first run and says nothing before that.
    """
    changed: List[str] = []
    dangling: List[str] = []
    out = json.loads(json.dumps(workflow))

    for node in out.get("nodes", []):
        node_name = str(node.get("name", "(unnamed node)"))
        node_type = str(node.get("type", ""))
        params = node.get("parameters") or {}

        if _is_sub_workflow_node(node_type):
            ref = _ref_id(params.get("workflowId"))
            if ref and ref in workflow_ids:
                params["workflowId"] = _set_ref_id(params["workflowId"], workflow_ids[ref],
                                                   workflow_names.get(ref))
                changed.append(f"{node_name}: Execute Workflow {ref} -> {workflow_ids[ref]}")
            elif ref:
                dangling.append(f"{node_name}: Execute Workflow target {ref} is not in the id map")
            else:
                dangling.append(f"{node_name}: Execute Workflow target is set by expression or name; check it by hand")

        for cred_type, cred in list((node.get("credentials") or {}).items()):
            if not isinstance(cred, dict) or not cred.get("id"):
                continue
            old = str(cred["id"])
            if old in cred_map:
                new = cred_map[old]
                node["credentials"][cred_type] = {"id": new["id"], "name": new["name"] or cred.get("name", "")}
                changed.append(f"{node_name}: credential {cred_type} {old} -> {new['id']}")
            else:
                dangling.append(f"{node_name}: credential {cred_type} {cred.get('name', '')} ({old}) has no entry in the credential map")

        for field in TABLE_ID_FIELDS:
            ref = _ref_id(params.get(field))
            if not ref:
                continue
            if ref in table_map:
                new = table_map[ref]
                params[field] = _set_ref_id(params[field], new["id"], new["name"])
                changed.append(f"{node_name}: data table {ref} -> {new['id']}")
            else:
                dangling.append(f"{node_name}: data table {ref} has no entry in the table map")

    settings = out.setdefault("settings", {})
    error_workflow = settings.get("errorWorkflow")
    if error_workflow:
        ref = str(error_workflow)
        if ref in workflow_ids:
            settings["errorWorkflow"] = workflow_ids[ref]
            changed.append(f"settings: errorWorkflow {ref} -> {workflow_ids[ref]}")
        else:
            dangling.append(f"settings: errorWorkflow {ref} is not in the id map")

    return out, changed, dangling


def cmd_repoint(args: argparse.Namespace) -> int:
    directory = pathlib.Path(args.directory)
    id_map_path = directory / "_id_map.json"
    if not id_map_path.is_file():
        sys.exit(f"{id_map_path} not found. Run import --confirm first; it writes the id map.")
    id_map = json.loads(id_map_path.read_text(encoding="utf-8"))
    workflow_ids = {old: str(v["new_id"]) for old, v in id_map.items() if v.get("new_id")}
    workflow_names = {old: str(v.get("name", "")) for old, v in id_map.items()}
    cred_map = _load_map(getattr(args, "credential_map", None))
    table_map = _load_map(getattr(args, "table_map", None))
    base, key = _env("N8N_TARGET_URL"), _env("N8N_TARGET_KEY")

    written = 0
    pending = 0
    still_pointing: List[Tuple[str, str]] = []
    for old, new_id in sorted(workflow_ids.items(), key=lambda kv: workflow_names.get(kv[0], "").lower()):
        name = workflow_names.get(old, old)
        full = _request(base, key, f"/api/v1/workflows/{new_id}")
        repointed, changed, dangling = _repoint_workflow(full, workflow_ids, workflow_names, cred_map, table_map)
        print(f"{name}  ({old} -> {new_id})")
        for line in changed:
            print(f"    {line}")
        for line in dangling:
            print(f"    STILL AT THE SOURCE: {line}")
            still_pointing.append((name, line))
        if not changed and not dangling:
            print("    nothing to repoint")
        if changed:
            if args.confirm:
                payload = {field: repointed[field] for field in CREATE_FIELDS if field in repointed}
                _request(base, key, f"/api/v1/workflows/{new_id}", method="PUT", payload=payload)
                written += 1
            else:
                pending += 1

    print()
    if args.confirm:
        print(f"Wrote {written} workflow(s) back to {base}. Nothing was activated.")
    else:
        print(f"{pending} workflow(s) would be written back. Nothing was written; re-run with --confirm.")
    if still_pointing:
        print(f"{len(still_pointing)} reference(s) still point at the source. Each one fails on")
        print("its first run on the target and says nothing before that:")
        for name, line in still_pointing:
            print(f"  {name}: {line}")
        return 2
    print("Every reference the tool understands now points at the target.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_export = sub.add_parser("export", help="pull every workflow from the source")
    p_export.add_argument("directory", help="directory to write the JSON into")
    p_export.set_defaults(func=cmd_export)

    p_inspect = sub.add_parser("inspect", help="report what does not travel with the workflows")
    p_inspect.add_argument("directory", help="directory holding the exported JSON")
    p_inspect.add_argument("--source-host", default=None,
                           help="host name of the source instance; defaults to N8N_SOURCE_URL's host, "
                                "else any host containing n8n.cloud")
    p_inspect.set_defaults(func=cmd_inspect)

    p_import = sub.add_parser("import", help="create the workflows on the target, always inactive")
    p_import.add_argument("directory", help="directory holding the exported JSON")
    p_import.add_argument("--confirm", action="store_true", help="actually create them")
    p_import.add_argument("--allow-existing", action="store_true",
                          help="proceed even though the target already has workflows")
    p_import.add_argument("--rewrite-host", action="append", metavar="OLD=NEW",
                          help="replace the literal OLD with NEW in every node parameter before "
                               "creating; repeatable; every touched node is printed")
    p_import.set_defaults(func=cmd_import)

    p_repoint = sub.add_parser("repoint", help="rewrite ids on the target from the maps")
    p_repoint.add_argument("directory", help="directory holding _id_map.json from import")
    p_repoint.add_argument("--credential-map", default=None,
                           help="JSON file {source credential id: target id or {id, name}}")
    p_repoint.add_argument("--table-map", default=None,
                           help="JSON file {source data table id: target id or {id, name}}")
    p_repoint.add_argument("--confirm", action="store_true", help="actually write the workflows back")
    p_repoint.set_defaults(func=cmd_repoint)

    args = parser.parse_args()
    try:
        return args.func(args)
    except ApiError as exc:
        sys.exit(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())

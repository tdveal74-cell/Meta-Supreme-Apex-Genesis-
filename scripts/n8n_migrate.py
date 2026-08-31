#!/usr/bin/env python3
"""Move an n8n estate between instances, without the silent failures.

Three subcommands, meant to be run in order:

    export    pull every workflow from the source instance to a directory
    inspect   report what the exported set needs that does NOT travel with it
    import    create the workflows on the target, always inactive

Credentials are read from the environment and never written to disk:

    N8N_SOURCE_URL   https://your-instance.app.n8n.cloud
    N8N_SOURCE_KEY   an API key on the source, needs workflow:list and :read
    N8N_TARGET_URL   https://n8n.your-host
    N8N_TARGET_KEY   an API key on the target, needs workflow:create

Why this exists rather than a shell one-liner. Four things do not move with a
workflow, and three of them fail silently rather than loudly:

  * Credentials are referenced by id. A fresh instance mints new ids, so every
    reference dangles until it is re-linked by hand. `inspect` lists them.
  * n8n data tables do not export with workflows at all. `inspect` names the
    ones your workflows read and write so you can rebuild them first.
  * Webhook URLs carry the host. Everything that POSTs to them keeps posting
    at the old one until it is repointed.
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
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Iterator, List, Optional, Tuple

TIMEOUT = 60

# n8n's create endpoint rejects the fields it owns. Everything not in this set
# is dropped on import: id, active, tags, createdAt, updatedAt, versionId,
# meta, pinData, shared, triggerCount and anything else the API adds later.
CREATE_FIELDS = ("name", "nodes", "connections", "settings")


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

def _scan(directory: pathlib.Path) -> Tuple[Dict[str, str], Dict[str, List[str]], Dict[str, List[str]], List[Dict[str, Any]]]:
    credentials: Dict[str, str] = {}          # id -> name
    webhooks: Dict[str, List[str]] = {}       # path -> [workflow names]
    tables: Dict[str, List[str]] = {}         # table id or name -> [workflow names]
    workflows: List[Dict[str, Any]] = []

    for path in sorted(directory.glob("*.json")):
        if path.name == "_index.json":
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        name = data.get("name", path.stem)
        workflows.append({"name": name, "id": data.get("id"), "active": data.get("active", False)})

        for node in data.get("nodes", []):
            for cred in (node.get("credentials") or {}).values():
                if isinstance(cred, dict) and cred.get("id"):
                    credentials[str(cred["id"])] = cred.get("name", "(unnamed)")

            params = node.get("parameters") or {}
            if "webhook" in str(node.get("type", "")).lower():
                wh = params.get("path")
                if wh:
                    webhooks.setdefault(str(wh), []).append(name)

            # Data table nodes reference the table by id, and some workflows
            # reach them over HTTP. Catch both shapes without guessing hard.
            for field in ("tableId", "dataTableId", "table"):
                value = params.get(field)
                if isinstance(value, str) and value:
                    tables.setdefault(value, []).append(name)
                elif isinstance(value, dict) and value.get("value"):
                    tables.setdefault(str(value["value"]), []).append(name)

    return credentials, webhooks, tables, workflows


def cmd_inspect(args: argparse.Namespace) -> int:
    directory = pathlib.Path(args.directory)
    if not directory.is_dir():
        sys.exit(f"{directory} is not a directory. Run export first.")

    credentials, webhooks, tables, workflows = _scan(directory)
    active = [w for w in workflows if w["active"]]

    print(f"{len(workflows)} workflow(s), {len(active)} active on the source.\n")

    print("CREDENTIALS referenced by id. A fresh target mints new ids, so each")
    print("of these must exist on the target and be re-linked by hand:")
    for cred_id, cred_name in sorted(credentials.items(), key=lambda kv: kv[1].lower()):
        print(f"  {cred_name}  ({cred_id})")
    if not credentials:
        print("  (none found)")

    print("\nWEBHOOK PATHS. Every one of these changes host on the target, and")
    print("anything posting to the old host keeps posting there until repointed:")
    for path, owners in sorted(webhooks.items()):
        collision = "  <-- SHARED BY MORE THAN ONE WORKFLOW" if len(owners) > 1 else ""
        print(f"  /{path}  ({', '.join(sorted(set(owners)))}){collision}")
    if not webhooks:
        print("  (none found)")

    print("\nDATA TABLES referenced. These do NOT export with workflows and must")
    print("be recreated on the target before anything that reads them runs:")
    for table, owners in sorted(tables.items()):
        print(f"  {table}  ({', '.join(sorted(set(owners)))})")
    if not tables:
        print("  (none detected; check by hand, node shapes vary by n8n version)")

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

    existing = list(_paged_workflows(base, key))
    if existing and not args.allow_existing:
        sys.exit(
            f"The target already has {len(existing)} workflow(s). A webhook path "
            "collision does not error in n8n, it silently routes to whichever "
            "workflow was published first, so importing onto a populated "
            "instance can hijack a live path. Re-run with --allow-existing only "
            "once you have checked for path collisions."
        )

    _, webhooks, _, _ = _scan(directory)
    if existing:
        taken: Dict[str, str] = {}
        for preview in existing:
            full = _request(base, key, f"/api/v1/workflows/{preview['id']}")
            for node in full.get("nodes", []):
                path = (node.get("parameters") or {}).get("path")
                if path and "webhook" in str(node.get("type", "")).lower():
                    taken[str(path)] = full.get("name", preview["id"])
        clashes = sorted(set(webhooks) & set(taken))
        if clashes:
            print("Refusing to import. These webhook paths already exist on the target:")
            for path in clashes:
                print(f"  /{path}  (held by {taken[path]})")
            return 2

    if not args.confirm:
        print(f"Would create {len(list(directory.glob('*.json'))) - 1} workflow(s) on {base}, all inactive.")
        print("Re-run with --confirm to actually create them.")
        return 0

    mapping: Dict[str, Dict[str, str]] = {}
    for path in sorted(directory.glob("*.json")):
        if path.name == "_index.json":
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        payload = {field: data[field] for field in CREATE_FIELDS if field in data}
        payload.setdefault("settings", {})
        created = _request(base, key, "/api/v1/workflows", method="POST", payload=payload)
        mapping[str(data.get("id"))] = {
            "name": data.get("name", ""),
            "new_id": str(created.get("id", "")),
            "was_active_on_source": bool(data.get("active", False)),
        }
        print(f"  created  {data.get('name')}  {data.get('id')} -> {created.get('id')}")

    out = directory / "_id_map.json"
    out.write_text(json.dumps(mapping, indent=2), encoding="utf-8")
    print(f"\nCreated {len(mapping)} workflow(s), all INACTIVE. Id map: {out}")
    print("Next, and in this order:")
    print("  1. Recreate credentials on the target and re-link them in each workflow.")
    print("  2. Recreate the data tables, then move their rows.")
    print("  3. Smoke one lane end to end while the source is still the live one.")
    print("  4. Deactivate on the source BEFORE activating here. Never both at once.")
    print("  5. Update services/devon/vault.py: N8N_HOST and every webhook entry.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_export = sub.add_parser("export", help="pull every workflow from the source")
    p_export.add_argument("directory", help="directory to write the JSON into")
    p_export.set_defaults(func=cmd_export)

    p_inspect = sub.add_parser("inspect", help="report what does not travel with the workflows")
    p_inspect.add_argument("directory", help="directory holding the exported JSON")
    p_inspect.set_defaults(func=cmd_inspect)

    p_import = sub.add_parser("import", help="create the workflows on the target, always inactive")
    p_import.add_argument("directory", help="directory holding the exported JSON")
    p_import.add_argument("--confirm", action="store_true", help="actually create them")
    p_import.add_argument("--allow-existing", action="store_true",
                          help="proceed even though the target already has workflows")
    p_import.set_defaults(func=cmd_import)

    args = parser.parse_args()
    try:
        return args.func(args)
    except ApiError as exc:
        sys.exit(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())

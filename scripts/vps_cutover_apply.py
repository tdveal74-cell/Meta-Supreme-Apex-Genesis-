"""Drive the VPS cutover rebuild over the n8n REST API, one organ at a time.

``vps_cutover_rebuild`` turns a Cloud workflow into a list of operations and
``vps_cutover_verify`` checks the result, but neither talks to n8n. Applying the
operations by hand through an MCP tool means every Code node body passes through
an agent's output twice, once into ``cloud.json`` and once into the update call.
Measured on 2026-09-15: of the four transcription hops that creates, three are
caught by the verifier and one is not. An error made reading Cloud into
``cloud.json`` flows into the operations, onto the VPS, and back into
``vps-after.json``, so the verifier compares two copies of the same error and
passes. This module removes all four hops: it reads both instances over HTTP,
applies the operations in memory, writes the result back over HTTP and verifies
it, so no workflow JSON is ever retyped.

It deliberately reuses ``build_operations`` rather than constructing the target
workflow itself. The transform is the tested part and it stays the only thing
deciding what a rebuilt organ looks like; this module only interprets what it
emits.

Environment::

    N8N_CLOUD_URL   default https://thequietoperator.app.n8n.cloud
    N8N_CLOUD_KEY   an n8n API key on Cloud, read is enough
    N8N_VPS_URL     default vault.N8N_HOST
    N8N_VPS_KEY     an n8n API key on the VPS, needs write

Usage::

    python3 scripts/vps_cutover_apply.py --organ capture-hook --dry-run
    python3 scripts/vps_cutover_apply.py --all --out .cutover

``--dry-run`` reads both instances, generates and applies the operations in
memory and runs the verifier against the result, without writing to the VPS. It
is the honest rehearsal: it answers "would this organ verify clean" without
touching anything live.

The webhook guard is not optional. Recreating a webhook node issues a new
``webhookId`` and breaks every caller holding the old URL, so every webhookId
present before the write is asserted still present and unchanged after it. A
violation fails the organ and says so; it does not warn and continue.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import vps_cutover_rebuild as rebuild  # noqa: E402
import vps_cutover_verify as verify  # noqa: E402

TIMEOUT = 30
CLOUD_URL_DEFAULT = "https://thequietoperator.app.n8n.cloud"


# --------------------------------------------------------------------------
# transport
# --------------------------------------------------------------------------


def api(base: str, key: str, path: str, method: str = "GET",
        payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """One n8n REST call. Raises with the response body, which names the field."""
    url = f"{base.rstrip('/')}/api/v1{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("X-N8N-API-KEY", key)
    request.add_header("Accept", "application/json")
    if data is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:600]
        raise RuntimeError(f"{method} {url} -> HTTP {exc.code}: {detail}") from exc
    return json.loads(body) if body else {}


# --------------------------------------------------------------------------
# the operation interpreter
# --------------------------------------------------------------------------


def _node(workflow: Dict[str, Any], name: str) -> Dict[str, Any]:
    for node in workflow["nodes"]:
        if node.get("name") == name:
            return node
    raise KeyError(f"operation names a node that is not in the workflow: {name}")


def _lane(workflow: Dict[str, Any], source: str, conn_type: str,
          lane_index: int) -> List[Dict[str, Any]]:
    lanes = workflow.setdefault("connections", {}).setdefault(source, {}).setdefault(conn_type, [])
    while len(lanes) <= lane_index:
        lanes.append([])
    return lanes[lane_index]


def apply_operations(workflow: Dict[str, Any],
                     operations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Apply what ``build_operations`` emits to a workflow dict, in order.

    Every operation type the generator can produce is handled. An unknown type
    raises rather than being skipped: a silently ignored operation is a rebuilt
    organ that verifies against the wrong thing.
    """
    result = copy.deepcopy(workflow)
    result.setdefault("nodes", [])
    result.setdefault("connections", {})

    for operation in operations:
        kind = operation.get("type")

        if kind == "updateNodeParameters":
            node = _node(result, operation["nodeName"])
            if operation.get("replace"):
                node["parameters"] = copy.deepcopy(operation["parameters"])
            else:
                node.setdefault("parameters", {}).update(copy.deepcopy(operation["parameters"]))

        elif kind == "setNodeCredential":
            node = _node(result, operation["nodeName"])
            node.setdefault("credentials", {})[operation["credentialKey"]] = {
                "id": operation["credentialId"],
                "name": operation["credentialName"],
            }

        elif kind == "setNodePosition":
            _node(result, operation["nodeName"])["position"] = list(operation["position"])

        elif kind == "setNodeDisabled":
            node = _node(result, operation["nodeName"])
            if operation["disabled"]:
                node["disabled"] = True
            else:
                node.pop("disabled", None)

        elif kind == "setNodeSettings":
            _node(result, operation["nodeName"]).update(copy.deepcopy(operation["settings"]))

        elif kind == "addNode":
            result["nodes"].append(copy.deepcopy(operation["node"]))

        elif kind == "removeNode":
            name = operation["nodeName"]
            result["nodes"] = [n for n in result["nodes"] if n.get("name") != name]
            result["connections"].pop(name, None)
            for lanes in result["connections"].values():
                for conn_type, lane_list in lanes.items():
                    lanes[conn_type] = [
                        [edge for edge in lane if edge.get("node") != name] for lane in lane_list
                    ]

        elif kind == "removeConnection":
            lane = _lane(result, operation["source"], operation["connectionType"],
                         operation["sourceIndex"])
            target, index = operation["target"], operation["targetIndex"]
            keep = [e for e in lane
                    if not (e.get("node") == target and e.get("index") == index)]
            lane[:] = keep

        elif kind == "addConnection":
            lane = _lane(result, operation["source"], operation["connectionType"],
                         operation["sourceIndex"])
            lane.append({
                "node": operation["target"],
                "type": operation["connectionType"],
                "index": operation["targetIndex"],
            })

        elif kind == "setWorkflowSettings":
            result.setdefault("settings", {}).update(copy.deepcopy(operation["settings"]))

        elif kind == "setWorkflowMetadata":
            result["description"] = operation["description"]

        else:
            raise ValueError(f"unknown operation type: {kind!r}")

    # Drop connection entries a rebuild emptied, so the shape matches a fresh read.
    for source in list(result["connections"]):
        lanes = result["connections"][source]
        for conn_type in list(lanes):
            while lanes[conn_type] and not lanes[conn_type][-1]:
                lanes[conn_type].pop()
            if not lanes[conn_type]:
                lanes.pop(conn_type)
        if not lanes:
            result["connections"].pop(source)

    return result


# --------------------------------------------------------------------------
# the webhook guard
# --------------------------------------------------------------------------


def webhook_ids(workflow: Dict[str, Any]) -> Dict[str, str]:
    return {
        node["name"]: node["webhookId"]
        for node in workflow.get("nodes", [])
        if node.get("webhookId")
    }


def check_webhook_ids(before: Dict[str, Any], after: Dict[str, Any]) -> List[str]:
    """Return one complaint per webhookId that moved or vanished."""
    was, now = webhook_ids(before), webhook_ids(after)
    complaints = []
    for name, value in was.items():
        if name not in now:
            complaints.append(f"{name}: webhookId {value} is gone from the rebuilt copy")
        elif now[name] != value:
            complaints.append(f"{name}: webhookId changed {value} -> {now[name]}")
    return complaints


# --------------------------------------------------------------------------
# one organ
# --------------------------------------------------------------------------


def put_workflow(base: str, key: str, workflow_id: str,
                 workflow: Dict[str, Any]) -> Dict[str, Any]:
    """Write a workflow back. n8n rejects read-only fields, so send only the four."""
    body = {
        "name": workflow["name"],
        "nodes": workflow["nodes"],
        "connections": workflow["connections"],
        "settings": workflow.get("settings") or {"executionOrder": "v1"},
    }
    return api(base, key, f"/workflows/{workflow_id}", method="PUT", payload=body)


def run_organ(organ: Dict[str, Any], maps: Dict[str, Any], out: pathlib.Path,
              cloud: Tuple[str, str], vps: Tuple[str, str],
              overlay_root: Optional[pathlib.Path], dry_run: bool) -> Dict[str, Any]:
    short = organ["short"]
    folder = out / short
    folder.mkdir(parents=True, exist_ok=True)
    outcome: Dict[str, Any] = {"organ": short, "name": organ["name"], "ok": False}

    cloud_payload = api(cloud[0], cloud[1], f"/workflows/{organ['cloud_id']}")
    vps_payload = api(vps[0], vps[1], f"/workflows/{organ['vps_id']}")
    folder.joinpath("cloud.json").write_text(json.dumps(cloud_payload, indent=1))
    folder.joinpath("vps-before.json").write_text(json.dumps(vps_payload, indent=1))

    cloud_wf = rebuild.unwrap(cloud_payload)
    vps_wf = rebuild.unwrap(vps_payload)

    overlay: Dict[str, pathlib.Path] = {}
    requested = bool(organ.get("overlay")) and overlay_root is not None
    if requested:
        directory = overlay_root / organ["overlay"]
        if not directory.is_dir():
            outcome["error"] = f"overlay directory is missing: {directory}"
            return outcome
        for path in sorted(directory.glob("*.js")):
            overlay[rebuild.overlay_key(path.stem)] = path

    report: Dict[str, Any] = {
        "cloud_id": organ["cloud_id"], "vps_id": organ["vps_id"], "name": organ["name"],
        "hits": {"host": 0, "workflow_ids": 0, "data_tables": 0},
        "overlay_requested": requested, "overlay_applied": [],
        "overlay_unmatched_files": [], "overlay_code_nodes_without_file": [],
        "type_version_mismatch": [], "credentials_mapped": [], "credentials_unmapped": [],
        "nodes_updated": [], "nodes_added": [], "nodes_removed": [], "settings": {},
    }
    node_ops, conn_ops = rebuild.build_operations(cloud_wf, vps_wf, maps, overlay, report)
    operations = node_ops + conn_ops
    report["op_count"] = len(operations)
    folder.joinpath("report.json").write_text(json.dumps(report, indent=1))
    outcome["report"] = report

    if report["overlay_unmatched_files"]:
        outcome["error"] = (
            "overlay_unmatched_files is not empty, so nothing was applied: "
            + ", ".join(report["overlay_unmatched_files"])
        )
        return outcome

    rebuilt = apply_operations(vps_wf, operations)
    folder.joinpath("vps-target.json").write_text(json.dumps(rebuilt, indent=1))

    complaints = check_webhook_ids(vps_wf, rebuilt)
    if complaints:
        outcome["error"] = "webhook guard: " + "; ".join(complaints)
        return outcome

    if dry_run:
        after = rebuilt
        outcome["dry_run"] = True
    else:
        put_workflow(vps[0], vps[1], organ["vps_id"], rebuilt)
        after_payload = api(vps[0], vps[1], f"/workflows/{organ['vps_id']}")
        folder.joinpath("vps-after.json").write_text(json.dumps(after_payload, indent=1))
        after = rebuild.unwrap(after_payload)
        complaints = check_webhook_ids(vps_wf, after)
        if complaints:
            outcome["error"] = "webhook guard after write: " + "; ".join(complaints)
            return outcome

    overlay_text: Dict[str, str] = {}
    if requested:
        for path in sorted((overlay_root / organ["overlay"]).glob("*.js")):
            overlay_text[rebuild.overlay_key(path.stem)] = path.read_text(encoding="utf-8")

    mismatches = verify.compare(cloud_wf, after, maps, overlay_text)
    outcome["verify"] = {
        "ok": not mismatches,
        "mismatches": mismatches,
        "cloud_nodes": len(cloud_wf.get("nodes", [])),
        "vps_nodes": len(after.get("nodes", [])),
        "cloud_edges": len(verify.connection_edges(cloud_wf)),
        "vps_edges": len(verify.connection_edges(after)),
    }
    folder.joinpath("verify.json").write_text(json.dumps(outcome["verify"], indent=1))
    outcome["ok"] = not mismatches
    if mismatches:
        outcome["error"] = f"verify reported {len(mismatches)} mismatches"
    return outcome


# --------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--organs", default="docs/devon/vps-cutover-organs_2026-09-15.json")
    parser.add_argument("--maps", default="docs/devon/vps-cutover-maps_2026-09-15.json")
    parser.add_argument("--overlay-root", default="n8n/devon")
    parser.add_argument("--out", default=".cutover")
    parser.add_argument("--organ", action="append", help="repeatable organ short name")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    cloud = (os.environ.get("N8N_CLOUD_URL", CLOUD_URL_DEFAULT), os.environ.get("N8N_CLOUD_KEY", ""))
    vps_url = os.environ.get("N8N_VPS_URL")
    if not vps_url:
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
        from services.devon import vault  # noqa: WPS433
        vps_url = vault.N8N_HOST
    vps = (vps_url, os.environ.get("N8N_VPS_KEY", ""))

    missing = [name for name, value in (("N8N_CLOUD_KEY", cloud[1]), ("N8N_VPS_KEY", vps[1]))
               if not value]
    if missing:
        print(json.dumps({"error": "unset: " + ", ".join(missing)}))
        return 2

    organs = json.loads(pathlib.Path(args.organs).read_text())
    if args.organ:
        wanted = set(args.organ)
        organs = [o for o in organs if o["short"] in wanted]
        unknown = wanted - {o["short"] for o in organs}
        if unknown:
            print(json.dumps({"error": "unknown organ: " + ", ".join(sorted(unknown))}))
            return 2
    elif not args.all:
        print(json.dumps({"error": "pass --organ <short> or --all"}))
        return 2

    maps = json.loads(pathlib.Path(args.maps).read_text())
    for key in ("workflow_ids", "data_tables", "credentials", "error_workflows"):
        maps.setdefault(key, {})

    out = pathlib.Path(args.out)
    overlay_root = pathlib.Path(args.overlay_root)
    results = []
    failed = 0
    for organ in organs:
        try:
            outcome = run_organ(organ, maps, out,
                                cloud, vps, overlay_root, args.dry_run)
        except Exception as exc:  # noqa: BLE001 - one organ failing must not stop the rest
            outcome = {"organ": organ["short"], "name": organ["name"], "ok": False,
                       "error": f"{type(exc).__name__}: {exc}"}
        results.append(outcome)
        failed += 0 if outcome["ok"] else 1
        print(json.dumps({k: outcome[k] for k in ("organ", "ok", "error") if k in outcome}))

    out.mkdir(parents=True, exist_ok=True)
    out.joinpath("summary.json").write_text(json.dumps(results, indent=1))
    print(json.dumps({"organs": len(results), "ok": len(results) - failed, "failed": failed}))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

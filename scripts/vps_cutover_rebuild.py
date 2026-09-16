"""Rebuild a VPS workflow from its n8n Cloud live version, with the cutover maps applied.

Ruled by Tee 2026-09-15: every DEVON organ runs on the VPS, live and published.
The VPS copies are a 2026-08-31 export plus a handful of 2026-09-10 rebuilds, so
most of them are stale against what Cloud is actually running. This module turns
the Cloud live version of one workflow into a list of ``update_workflow``
operations that make the VPS copy match it, with every Cloud identifier rewritten
to its VPS twin.

Nothing here talks to n8n. It reads two ``get_workflow_details`` payloads from
disk and writes operation files; a caller applies them through the MCP tool and
then checks the result with ``vps_cutover_verify``. That split is deliberate:
the transform is the part worth testing offline, and a generated operation list
is a thing a human can read before it is applied to a live instance.

Usage::

    python3 scripts/vps_cutover_rebuild.py \\
        --cloud cloud.json --vps vps-before.json \\
        --maps docs/devon/vps-cutover-maps_2026-09-15.json \\
        --out ops --chunk 90 [--overlay n8n/devon/<organ>]

``cloud.json`` and ``vps-before.json`` are ``get_workflow_details`` results; the
workflow object may sit under a ``workflow`` key or be the payload itself.
``--maps`` carries ``host_from``, ``host_to``, ``workflow_ids``, ``credentials``,
``data_tables`` and ``error_workflows``. ``--overlay`` points at a directory of
repository Code node bodies (``n8n/devon/<organ>/``); a file whose stem matches a
Code node name replaces that node's ``jsCode``, so edits made in the repository
win over the Cloud text.

The strategy keeps webhook ids alive. A node present on both sides under the same
name and type is updated in place, because recreating a webhook node would issue a
new ``webhookId`` and break every caller holding the old URL. A node only on Cloud
is added, a node only on the VPS is removed, and every VPS connection is dropped
and rebuilt from the Cloud graph.

Outputs ``<out>/ops-N.json`` (at most ``--chunk`` operations each, node operations
first and connection operations last) and ``<out>/report.json``, which names what
was mapped, what could not be, and which overlay files matched.

One operation type, ``setNodeTypeVersion``, is read by ``vps_cutover_apply`` and
may not be understood by the n8n MCP ``update_workflow`` tool. Applying these
operations over REST with that driver is the supported path; an MCP caller that
does not know the type will reject the batch loudly rather than skip it.
"""

from __future__ import annotations

import argparse
import copy
import json
import pathlib
import re
from typing import Any, Dict, List, Optional, Tuple

#: Per-node settings n8n keeps beside the parameters. They are carried across
#: because ``alwaysOutputData`` and ``onError`` change what a graph does.
NODE_SETTING_KEYS: Tuple[str, ...] = (
    "alwaysOutputData",
    "executeOnce",
    "retryOnFail",
    "maxTries",
    "waitBetweenTries",
    "onError",
)

#: Workflow settings copied from the Cloud version verbatim. ``errorWorkflow``
#: and ``callerIds`` are handled separately because they carry workflow ids.
WORKFLOW_SETTING_KEYS: Tuple[str, ...] = (
    "executionOrder",
    "saveDataSuccessExecution",
    "saveDataErrorExecution",
    "saveManualExecutions",
    "saveExecutionProgress",
    "executionTimeout",
    "timezone",
    "callerPolicy",
)


def unwrap(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Return the workflow object, whether or not it sits under a ``workflow`` key."""
    if isinstance(payload, dict) and "workflow" in payload and "nodes" in payload["workflow"]:
        return payload["workflow"]
    return payload


def overlay_key(name: str) -> str:
    """The comparison key that matches a node name to a repository file stem.

    ``Validate and Plan`` and ``validate_and_plan.js`` both reduce to
    ``validate_and_plan``, so the repository copies match their nodes without a
    hand written table.
    """
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def rewrite_strings(value: Any, maps: Dict[str, Any], hits: Dict[str, int]) -> Any:
    """Rewrite every Cloud identifier inside a parameter tree to its VPS twin.

    The search runs over string VALUES wherever they sit, not only over the URL
    field, because the Action Router keeps its executor URLs and workflow ids
    inside a Code node body and the Approval Queue builds its email links from a
    HOST constant. A rewrite that only read ``parameters.url`` would leave both
    pointing at Cloud and nothing would notice until a live run.
    """
    if isinstance(value, str):
        out = value
        if maps["host_from"] in out:
            hits["host"] += out.count(maps["host_from"])
            out = out.replace(maps["host_from"], maps["host_to"])
        for cloud_id, vps_id in maps["workflow_ids"].items():
            if cloud_id in out:
                hits["workflow_ids"] += out.count(cloud_id)
                out = out.replace(cloud_id, vps_id)
        for cloud_id, vps_id in maps["data_tables"].items():
            if cloud_id in out:
                hits["data_tables"] += out.count(cloud_id)
                out = out.replace(cloud_id, vps_id)
        return out
    if isinstance(value, list):
        return [rewrite_strings(item, maps, hits) for item in value]
    if isinstance(value, dict):
        return {key: rewrite_strings(item, maps, hits) for key, item in value.items()}
    return value


def map_credentials(
    credentials: Optional[Dict[str, Any]],
    maps: Dict[str, Any],
    node_name: str,
    report: Dict[str, Any],
) -> Dict[str, Dict[str, str]]:
    """Rebind a node's credentials to the VPS ids, recording anything unmapped.

    A credential that has no VPS twin is never guessed at. It is left off the
    node and named in the report, because a node silently bound to the wrong
    account is worse than a node that refuses.
    """
    out: Dict[str, Dict[str, str]] = {}
    for cred_type, ref in (credentials or {}).items():
        cloud_id = str(ref.get("id", ""))
        target = maps["credentials"].get(cloud_id)
        if target:
            out[cred_type] = {
                "id": target["id"],
                "name": target.get("name", ref.get("name", "")),
            }
            report["credentials_mapped"].append(
                {
                    "node": node_name,
                    "type": cred_type,
                    "cloud_id": cloud_id,
                    "vps_id": target["id"],
                }
            )
        else:
            report["credentials_unmapped"].append(
                {
                    "node": node_name,
                    "type": cred_type,
                    "cloud_id": cloud_id,
                    "cloud_name": ref.get("name", ""),
                }
            )
    return out


def connection_edges(workflow: Dict[str, Any]) -> List[Tuple[str, str, int, str, int]]:
    """Flatten an n8n connection map into comparable edges."""
    edges: List[Tuple[str, str, int, str, int]] = []
    for source, outputs in (workflow.get("connections") or {}).items():
        for conn_type, lanes in outputs.items():
            for lane_index, lane in enumerate(lanes or []):
                for edge in lane or []:
                    edges.append(
                        (source, conn_type, lane_index, edge["node"], edge.get("index", 0))
                    )
    return edges


def build_operations(
    cloud: Dict[str, Any],
    vps: Dict[str, Any],
    maps: Dict[str, Any],
    overlay: Dict[str, pathlib.Path],
    report: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Return the node operations and the connection operations, in that order."""
    hits = report["hits"]
    vps_nodes = {node["name"]: node for node in vps.get("nodes", [])}
    node_ops: List[Dict[str, Any]] = []
    conn_ops: List[Dict[str, Any]] = []

    for source, conn_type, lane_index, target, target_index in connection_edges(vps):
        conn_ops.append(
            {
                "type": "removeConnection",
                "source": source,
                "target": target,
                "sourceIndex": lane_index,
                "targetIndex": target_index,
                "connectionType": conn_type,
            }
        )

    cloud_names = set()
    for node in cloud.get("nodes", []):
        name = node["name"]
        cloud_names.add(name)
        parameters = rewrite_strings(copy.deepcopy(node.get("parameters", {})), maps, hits)

        if node["type"] == "n8n-nodes-base.code":
            key = overlay_key(name)
            if key in overlay:
                parameters["jsCode"] = overlay.pop(key).read_text(encoding="utf-8")
                report["overlay_applied"].append(name)
            elif overlay or report["overlay_requested"]:
                report["overlay_code_nodes_without_file"].append(name)

        credentials = map_credentials(node.get("credentials"), maps, name, report)
        existing = vps_nodes.get(name)

        if existing is not None and existing.get("type") == node["type"]:
            node_ops.append(
                {
                    "type": "updateNodeParameters",
                    "nodeName": name,
                    "replace": True,
                    "parameters": parameters,
                }
            )
            if existing.get("typeVersion") != node.get("typeVersion"):
                report["type_version_mismatch"].append(
                    {
                        "node": name,
                        "cloud": node.get("typeVersion"),
                        "vps": existing.get("typeVersion"),
                    }
                )
                # Carry the version across, not just record it. The parameters
                # written just above are Cloud's, and they belong to Cloud's
                # typeVersion; leaving the VPS node on an older one applies new
                # parameters to old semantics, which is the more dangerous half
                # of the drift. Found 2026-09-15: six nodes in the Gumroad organ
                # verified dirty for exactly this, and nothing else in the estate
                # drifts, so the blast radius of the carry is one organ.
                node_ops.append(
                    {
                        "type": "setNodeTypeVersion",
                        "nodeName": name,
                        "typeVersion": node.get("typeVersion"),
                    }
                )
            for cred_type, ref in credentials.items():
                node_ops.append(
                    {
                        "type": "setNodeCredential",
                        "nodeName": name,
                        "credentialKey": cred_type,
                        "credentialId": ref["id"],
                        "credentialName": ref["name"],
                    }
                )
            node_ops.append(
                {
                    "type": "setNodePosition",
                    "nodeName": name,
                    "position": node.get("position", [0, 0]),
                }
            )
            report["nodes_updated"].append(name)
            if bool(existing.get("disabled")) != bool(node.get("disabled")):
                node_ops.append(
                    {
                        "type": "setNodeDisabled",
                        "nodeName": name,
                        "disabled": bool(node.get("disabled")),
                    }
                )
        else:
            if existing is not None:
                node_ops.append({"type": "removeNode", "nodeName": name})
                report["nodes_removed"].append(name + " (type changed)")
            fresh: Dict[str, Any] = {
                "name": name,
                "type": node["type"],
                "typeVersion": node.get("typeVersion", 1),
                "position": node.get("position", [0, 0]),
                "parameters": parameters,
            }
            if node.get("id"):
                fresh["id"] = node["id"]
            if node.get("notes"):
                fresh["notes"] = node["notes"]
            if credentials:
                fresh["credentials"] = credentials
            if node.get("disabled"):
                fresh["disabled"] = True
            node_ops.append({"type": "addNode", "node": fresh})
            report["nodes_added"].append(name)

        settings = {key: node[key] for key in NODE_SETTING_KEYS if key in node}
        if settings:
            node_ops.append({"type": "setNodeSettings", "nodeName": name, "settings": settings})

    for name in vps_nodes:
        if name not in cloud_names:
            node_ops.append({"type": "removeNode", "nodeName": name})
            report["nodes_removed"].append(name)

    report["overlay_unmatched_files"] = [str(path) for path in overlay.values()]

    for source, conn_type, lane_index, target, target_index in connection_edges(cloud):
        conn_ops.append(
            {
                "type": "addConnection",
                "source": source,
                "target": target,
                "sourceIndex": lane_index,
                "targetIndex": target_index,
                "connectionType": conn_type,
            }
        )

    cloud_settings = cloud.get("settings") or {}
    settings = {key: cloud_settings[key] for key in WORKFLOW_SETTING_KEYS if key in cloud_settings}
    if "callerIds" in cloud_settings:
        wanted = []
        for raw in str(cloud_settings["callerIds"]).split(","):
            caller = raw.strip()
            if caller:
                wanted.append(maps["workflow_ids"].get(caller, caller))
        settings["callerIds"] = ",".join(wanted)
    if cloud_settings.get("errorWorkflow"):
        cloud_error = cloud_settings["errorWorkflow"]
        mapped = maps["error_workflows"].get(cloud_error) or maps["workflow_ids"].get(cloud_error)
        if mapped:
            settings["errorWorkflow"] = mapped
        else:
            report["settings"]["error_workflow_unmapped"] = cloud_error
    if settings:
        conn_ops.append({"type": "setWorkflowSettings", "settings": settings})
    report["settings"]["applied"] = settings

    if cloud.get("description"):
        conn_ops.append(
            {"type": "setWorkflowMetadata", "description": str(cloud["description"])[:255]}
        )

    return node_ops, conn_ops


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cloud", required=True, help="get_workflow_details result from Cloud")
    parser.add_argument("--vps", required=True, help="get_workflow_details result from the VPS")
    parser.add_argument("--maps", required=True, help="the cutover identity maps JSON")
    parser.add_argument("--out", required=True, help="directory for the operation files")
    parser.add_argument("--chunk", type=int, default=90, help="operations per file, max 100")
    parser.add_argument(
        "--overlay",
        default="",
        help="directory of repository Code node bodies that win over the Cloud text",
    )
    args = parser.parse_args(argv)

    cloud = unwrap(json.load(open(args.cloud, encoding="utf-8")))
    vps = unwrap(json.load(open(args.vps, encoding="utf-8")))
    maps = json.load(open(args.maps, encoding="utf-8"))
    for key in ("workflow_ids", "data_tables", "credentials", "error_workflows"):
        maps.setdefault(key, {})

    overlay: Dict[str, pathlib.Path] = {}
    if args.overlay:
        for path in pathlib.Path(args.overlay).glob("*.js"):
            overlay[overlay_key(path.stem)] = path

    report: Dict[str, Any] = {
        "cloud_id": cloud.get("id"),
        "vps_id": vps.get("id"),
        "name": cloud.get("name"),
        "hits": {"host": 0, "workflow_ids": 0, "data_tables": 0},
        "overlay_requested": bool(args.overlay),
        "overlay_applied": [],
        "overlay_unmatched_files": [],
        "overlay_code_nodes_without_file": [],
        "type_version_mismatch": [],
        "credentials_mapped": [],
        "credentials_unmapped": [],
        "nodes_updated": [],
        "nodes_added": [],
        "nodes_removed": [],
        "settings": {},
    }

    node_ops, conn_ops = build_operations(cloud, vps, maps, overlay, report)
    operations = node_ops + conn_ops

    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.glob("ops-*.json"):
        stale.unlink()
    chunks = 0
    for start in range(0, len(operations), args.chunk):
        chunks += 1
        chunk = operations[start : start + args.chunk]
        (out_dir / f"ops-{chunks}.json").write_text(
            json.dumps(chunk, ensure_ascii=False), encoding="utf-8"
        )
    report["op_count"] = len(operations)
    report["chunks"] = chunks
    (out_dir / "report.json").write_text(
        json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8"
    )

    summary = {key: report[key] for key in ("name", "cloud_id", "vps_id", "hits", "op_count", "chunks")}
    print(json.dumps(summary, ensure_ascii=False))
    print(
        "updated {} added {} removed {} | credentials mapped {} unmapped {} | overlay applied {}".format(
            len(report["nodes_updated"]),
            len(report["nodes_added"]),
            len(report["nodes_removed"]),
            len(report["credentials_mapped"]),
            len(report["credentials_unmapped"]),
            len(report["overlay_applied"]),
        )
    )
    if report["overlay_unmatched_files"]:
        print("STOP: overlay files with no matching node:", report["overlay_unmatched_files"])
        return 2
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

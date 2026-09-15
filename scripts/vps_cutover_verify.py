"""Check a rebuilt VPS workflow against its n8n Cloud source, with the maps applied.

The companion to ``vps_cutover_rebuild``. That module writes operations; a caller
applies them through the MCP tool; this one reads the VPS copy back and answers
one question honestly: does it now match the Cloud live version once every Cloud
identifier is rewritten to its VPS twin.

It exists because an ``update_workflow`` call that reports ``appliedOperations``
has told you it accepted the operations, not that the workflow means the same
thing. A chunk that silently dropped a connection, a credential that failed to
bind, a Cloud host left inside a Code node body: all of those return a cheerful
success and a broken organ. Green is not correct.

Usage::

    python3 scripts/vps_cutover_verify.py \\
        --cloud cloud.json --vps vps-after.json \\
        --maps docs/devon/vps-cutover-maps_2026-09-15.json \\
        [--overlay n8n/devon/<organ>]

Prints a JSON report and exits non-zero when anything differs, so it can gate a
publish step rather than decorate one.
"""

from __future__ import annotations

import argparse
import copy
import json
import pathlib
import sys
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(pathlib.Path(__file__).parent))

from vps_cutover_rebuild import (  # noqa: E402
    NODE_SETTING_KEYS,
    WORKFLOW_SETTING_KEYS,
    connection_edges,
    overlay_key,
    rewrite_strings,
    unwrap,
)


def compare(
    cloud: Dict[str, Any],
    vps: Dict[str, Any],
    maps: Dict[str, Any],
    overlay: Dict[str, str],
) -> List[str]:
    """Return one line per difference between the rebuilt copy and the mapped source."""
    hits = {"host": 0, "workflow_ids": 0, "data_tables": 0}
    mismatches: List[str] = []
    vps_nodes = {node["name"]: node for node in vps.get("nodes", [])}
    cloud_names = set()

    for node in cloud.get("nodes", []):
        name = node["name"]
        cloud_names.add(name)
        got = vps_nodes.get(name)
        if got is None:
            mismatches.append(f"node missing on VPS: {name}")
            continue
        if got.get("type") != node.get("type"):
            mismatches.append(f"type differs: {name}")
        if got.get("typeVersion") != node.get("typeVersion"):
            mismatches.append(
                f"typeVersion differs: {name} cloud {node.get('typeVersion')} "
                f"vps {got.get('typeVersion')}"
            )

        want = rewrite_strings(copy.deepcopy(node.get("parameters", {})), maps, hits)
        if node["type"] == "n8n-nodes-base.code":
            key = overlay_key(name)
            if key in overlay:
                want["jsCode"] = overlay[key]
        have = got.get("parameters", {})
        if want != have:
            differing = sorted(
                key for key in set(want) | set(have) if want.get(key) != have.get(key)
            )
            mismatches.append(f"parameters differ: {name} keys {differing}")

        wanted_creds = {}
        for cred_type, ref in (node.get("credentials") or {}).items():
            target = maps["credentials"].get(str(ref.get("id", "")))
            if target:
                wanted_creds[cred_type] = target["id"]
        have_creds = {
            cred_type: str(ref.get("id", ""))
            for cred_type, ref in (got.get("credentials") or {}).items()
        }
        for cred_type, cred_id in wanted_creds.items():
            if have_creds.get(cred_type) != cred_id:
                mismatches.append(
                    f"credential differs: {name} {cred_type} "
                    f"want {cred_id} got {have_creds.get(cred_type)}"
                )

        for key in NODE_SETTING_KEYS:
            if node.get(key) is not None and node.get(key) != got.get(key):
                mismatches.append(
                    f"node setting differs: {name} {key} cloud {node.get(key)} vps {got.get(key)}"
                )
        if bool(node.get("disabled")) != bool(got.get("disabled")):
            mismatches.append(f"disabled differs: {name}")

    for name in vps_nodes:
        if name not in cloud_names:
            mismatches.append(f"extra node on VPS: {name}")

    cloud_edges = set(connection_edges(cloud))
    vps_edges = set(connection_edges(vps))
    for edge in sorted(cloud_edges - vps_edges):
        mismatches.append(f"connection missing on VPS: {edge}")
    for edge in sorted(vps_edges - cloud_edges):
        mismatches.append(f"extra connection on VPS: {edge}")

    cloud_settings = cloud.get("settings") or {}
    vps_settings = vps.get("settings") or {}
    for key in WORKFLOW_SETTING_KEYS:
        if key in cloud_settings and cloud_settings.get(key) != vps_settings.get(key):
            mismatches.append(
                f"setting differs: {key} cloud {cloud_settings.get(key)} "
                f"vps {vps_settings.get(key)}"
            )
    if cloud_settings.get("errorWorkflow"):
        cloud_error = cloud_settings["errorWorkflow"]
        want = maps["error_workflows"].get(cloud_error) or maps["workflow_ids"].get(cloud_error)
        if want and vps_settings.get("errorWorkflow") != want:
            mismatches.append(
                f"errorWorkflow differs: want {want} got {vps_settings.get('errorWorkflow')}"
            )

    leftover = json.dumps(vps.get("nodes", [])).count(maps["host_from"])
    if leftover:
        mismatches.append(f"{leftover} occurrences of the Cloud host remain on the VPS copy")

    return mismatches


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cloud", required=True)
    parser.add_argument("--vps", required=True)
    parser.add_argument("--maps", required=True)
    parser.add_argument("--overlay", default="")
    args = parser.parse_args(argv)

    cloud = unwrap(json.load(open(args.cloud, encoding="utf-8")))
    vps = unwrap(json.load(open(args.vps, encoding="utf-8")))
    maps = json.load(open(args.maps, encoding="utf-8"))
    for key in ("workflow_ids", "data_tables", "credentials", "error_workflows"):
        maps.setdefault(key, {})

    overlay: Dict[str, str] = {}
    if args.overlay:
        for path in pathlib.Path(args.overlay).glob("*.js"):
            overlay[overlay_key(path.stem)] = path.read_text(encoding="utf-8")

    mismatches = compare(cloud, vps, maps, overlay)
    report = {
        "ok": not mismatches,
        "mismatches": mismatches,
        "cloud_nodes": len(cloud.get("nodes", [])),
        "vps_nodes": len(vps.get("nodes", [])),
        "cloud_edges": len(connection_edges(cloud)),
        "vps_edges": len(connection_edges(vps)),
    }
    print(json.dumps(report, indent=1, ensure_ascii=False))
    return 0 if not mismatches else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

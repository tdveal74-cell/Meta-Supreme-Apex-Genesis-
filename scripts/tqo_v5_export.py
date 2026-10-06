"""Export both versions of TQO FINAL V5 from the n8n VPS into the repository.

The workflow carries two graphs at once: the published version, which is the
only one that runs, and the draft, which is what the editor shows and what a
session pulling the workflow reads. On 2026-10-06 those differed by 25 nodes
and every count a session had written down was the draft's. This script
writes one file per version under ``n8n/tqo-v5/exports/`` so the difference
is a diff rather than a sentence, and so a ruling to publish or discard a
draft is taken against a record of both.

Usage::

    python3 scripts/tqo_v5_export.py            # reads N8N_VPS_URL and N8N_VPS_KEY
    python3 scripts/tqo_v5_export.py --from FILE  # re-export from a saved API read

Nothing here writes to the instance. The public API GET returns the draft at
the top level and the published version under ``activeVersion``; when the two
version ids are equal there is no unpublished draft and both files carry the
same graph, which is the state the test wants to see after a publish.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import sys
import urllib.request

WORKFLOW_ID = "qEkGOUsNyVaRAmm6"
EXPORTS = pathlib.Path(__file__).resolve().parent.parent / "n8n" / "tqo-v5" / "exports"


def _read_live() -> tuple[dict, str]:
    base = os.environ.get("N8N_VPS_URL", "").rstrip("/")
    key = os.environ.get("N8N_VPS_KEY", "")
    if not base or not key:
        sys.exit("N8N_VPS_URL and N8N_VPS_KEY must be set")
    request = urllib.request.Request(
        f"{base}/api/v1/workflows/{WORKFLOW_ID}", headers={"X-N8N-API-KEY": key}
    )
    with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310
        payload = json.load(response)
    read_at = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return payload, read_at


def _shape(payload: dict, role: str, read_at: str) -> dict:
    if role == "draft":
        graph = payload
        version_id = payload["versionId"]
        stamp = payload.get("updatedAt")
    else:
        graph = payload["activeVersion"]
        version_id = payload["activeVersionId"]
        stamp = graph.get("createdAt") or graph.get("activatedAt")
    return {
        "workflowId": payload["id"],
        "name": payload["name"],
        "role": role,
        "versionId": version_id,
        "versionStamp": stamp,
        "versionDescription": graph.get("description"),
        "readAt": read_at,
        "active": payload.get("active"),
        "settings": payload.get("settings"),
        "nodes": graph["nodes"],
        "connections": graph["connections"],
    }


def export(payload: dict, read_at: str) -> list[pathlib.Path]:
    EXPORTS.mkdir(parents=True, exist_ok=True)
    written = []
    for role in ("active", "draft"):
        shaped = _shape(payload, role, read_at)
        path = EXPORTS / f"{WORKFLOW_ID}_{role}.json"
        path.write_text(json.dumps(shaped, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
        written.append(path)
        print(f"{role}: {shaped['versionId']} nodes={len(shaped['nodes'])} -> {path.name}")
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--from", dest="source", help="a saved GET /api/v1/workflows/{id} body")
    args = parser.parse_args()
    if args.source:
        payload = json.loads(pathlib.Path(args.source).read_text())
        read_at = dt.datetime.fromtimestamp(
            pathlib.Path(args.source).stat().st_mtime, dt.timezone.utc
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        payload, read_at = _read_live()
    if "activeVersion" not in payload:
        sys.exit("the API body carries no activeVersion; nothing to export for the published side")
    export(payload, read_at)


if __name__ == "__main__":
    main()

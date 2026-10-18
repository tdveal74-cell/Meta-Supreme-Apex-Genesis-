#!/usr/bin/env python3
"""Offline by default; optional one-query DEVON adapter readback, no persistence.

Run with PYTHONPATH=. from the repository root. --no-capture-reviewed records
an operator assertion about an independently reviewed provider/workspace
configuration. It is not proof, does not disable capture, and grants no rights.
No OAuth flow, refresh exchange, configuration update or memory ingestion runs.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re

from services.agent_runtime.tools import ToolRegistry
from services.graphify.agent_adapter import GraphifyCapabilityAdapter
from services.graphify.client import REPOSITORY, GraphifyMCPClient

QUESTION = "Locate DEVON approval enforcement and show its source paths and indexed commit."


async def check(*, live=False, no_capture_reviewed=False, client_factory=GraphifyMCPClient):
    enabled = os.getenv("DEVON_GRAPHIFY_ENABLED", "").lower() in {"1", "true", "yes", "on"}
    configured = enabled and bool(os.getenv("DEVON_GRAPHIFY_ACCESS_TOKEN", "").strip())
    receipt = {
        "mode": "live" if live else "offline-preflight",
        "repository": REPOSITORY,
        "configured": configured,
        "adapter_query_attempted": False,
        "authenticated_readback_verified": False,
        "remote_nonmutation_verified": False,
    }
    if not live:
        return 0, receipt
    if not configured or not no_capture_reviewed:
        receipt["status"] = "blocked: service credentials and independent no-capture review required"
        return 2, receipt
    registry = ToolRegistry()
    GraphifyCapabilityAdapter(client_factory).register(registry)
    receipt["adapter_query_attempted"] = True
    result = await registry.execute("graphify.query_graph", {"question": QUESTION})
    # Never print remote error text, code bodies, credentials or exception details.
    if not result.ok:
        receipt["status"] = "refused: adapter did not return successful evidence"
        return 3, receipt
    try:
        evidence = json.loads(result.output)
        metadata = result.metadata or {}
        commit = evidence.get("index_commit")
        context = evidence.get("content")
        if (evidence.get("kind") != "untrusted_external_code_evidence"
                or evidence.get("repository") != REPOSITORY
                or metadata.get("source") != "graphify"
                or metadata.get("authority") != "source-only"
                or not isinstance(commit, str)
                or not re.fullmatch(r"[a-fA-F0-9]{7,40}", commit)
                or not isinstance(context, str)):
            raise ValueError("invalid provenance")
        # Report source paths only; retrieved code/instructions remain withheld.
        paths = sorted(set(re.findall(r"(?:services|app|deploy|scripts)/[A-Za-z0-9_./-]+\.py", context)))[:20]
        if not paths:
            raise ValueError("no source paths")
        token = os.getenv("DEVON_GRAPHIFY_ACCESS_TOKEN", "").strip()
        if token and token in json.dumps([commit, paths]):
            raise ValueError("credential-shaped provenance withheld")
    except (ValueError, TypeError, AttributeError):
        receipt["status"] = "refused: source paths or indexed commit unverified"
        return 4, receipt
    receipt.update({
        "status": "adapter readback verified; nonmutation and index currency still require separate checks",
        "authenticated_readback_verified": True,
        "source": "graphify",
        "authority": "source-only",
        "index_commit": commit,
        "source_paths": paths,
        "truncated": bool(evidence.get("truncated")),
    })
    return 0, receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--no-capture-reviewed", action="store_true")
    args = parser.parse_args()
    try:
        status, receipt = asyncio.run(check(live=args.live, no_capture_reviewed=args.no_capture_reviewed))
    except Exception:
        status, receipt = 3, {"status": "readback failed; details withheld"}
    print(json.dumps(receipt, sort_keys=True))
    return status


if __name__ == "__main__":
    raise SystemExit(main())

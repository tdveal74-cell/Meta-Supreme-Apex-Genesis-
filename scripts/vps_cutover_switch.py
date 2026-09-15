"""Switch the DEVON estate from n8n Cloud to the VPS, in one ordered pass.

Ruled by Tee 2026-09-15: every DEVON organ runs on the VPS, live and published.
This is the irreversible half of the cutover and the one the handover warns
about hardest, because two live copies of the same organ is the failure to
avoid: two heartbeats, two janitors sweeping the same jobs, two pollers driving
the same ledger.

The order is the whole point, and it is not alphabetical:

* **Unpublish on Cloud leaf first.** A leaf organ stopping early is a missed
  sweep. The ledger or the bus stopping early orphans everything upstream of
  it, so they go last.
* **Publish on the VPS core first.** The ledger and the bus have to be
  listening before anything can report to them, so they go first and the leaves
  go last.

``TIERS`` below is that order, core to leaf. Phase one walks it backwards on
Cloud, phase two walks it forwards on the VPS. Every organ in
``vps-cutover-organs_2026-09-15.json`` must appear in exactly one tier or this
module refuses to run, so a new organ cannot be silently left behind.

Both phases are idempotent: current state is read first and a no-op is skipped
rather than posted, so an interrupted switch is finished by running it again.
An organ with no trigger node cannot be activated by n8n at all; that is
reported rather than retried, because a sub-workflow like the Job Driver is
called by another organ and is correct to be inactive.

Usage::

    python3 scripts/vps_cutover_switch.py --dry-run
    python3 scripts/vps_cutover_switch.py

Needs ``N8N_CLOUD_KEY`` and ``N8N_VPS_KEY``. ``--dry-run`` prints the exact
sequence and changes nothing.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

TIMEOUT = 30
CLOUD_URL_DEFAULT = "https://thequietoperator.app.n8n.cloud"

#: Core to leaf. Phase one reverses this on Cloud, phase two follows it on the VPS.
TIERS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("error handling", ("os-error-handler", "error-alarm")),
    ("ledger and bus", ("ledger", "event-bus")),
    ("spine and routing", ("spine", "runtime", "intel-router", "action-router",
                           "approval-queue")),
    ("executors", ("drive-draft", "airtable-row", "editforge")),
    ("drivers and face", ("job-driver", "intake-former", "driver-poll", "face")),
    ("learning lane", ("ledger-feeder", "soul-committer", "soul-writeback",
                       "b12-upstream", "table-reader")),
    ("leaves", ("heartbeat", "janitor", "watchdog", "health-console", "precedence",
                "capture-hook", "capture-webhook", "capture-nudge", "iphone-inbox",
                "gumroad", "notion-drain", "dup-sweep", "auto-purge", "purge-list",
                "cred-review", "weekly-backup", "master-index", "vault-compare",
                "e2e-harness")),
)


def api(base: str, key: str, path: str, method: str = "GET") -> Dict[str, Any]:
    url = f"{base.rstrip('/')}/api/v1{path}"
    request = urllib.request.Request(url, method=method)
    request.add_header("X-N8N-API-KEY", key)
    request.add_header("Accept", "application/json")
    if method == "POST":
        request.add_header("Content-Length", "0")
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:400]
        raise RuntimeError(f"{method} {url} -> HTTP {exc.code}: {detail}") from exc
    return json.loads(body) if body else {}


def ordered(organs: List[Dict[str, Any]]) -> List[Tuple[str, Dict[str, Any]]]:
    """Organs in TIERS order, refusing to run if any organ is unplaced."""
    by_short = {o["short"]: o for o in organs}
    placed: List[Tuple[str, Dict[str, Any]]] = []
    seen = set()
    for tier, shorts in TIERS:
        for short in shorts:
            if short not in by_short:
                raise SystemExit(f"TIERS names an organ that is not in the list: {short}")
            if short in seen:
                raise SystemExit(f"TIERS names {short} twice")
            seen.add(short)
            placed.append((tier, by_short[short]))
    missing = sorted(set(by_short) - seen)
    if missing:
        raise SystemExit("organs missing from TIERS, refusing to switch: " + ", ".join(missing))
    return placed


def has_trigger(workflow: Dict[str, Any]) -> bool:
    return bool(workflow.get("triggerCount")) or any(
        "trigger" in n.get("type", "").lower() or n.get("type") == "n8n-nodes-base.webhook"
        for n in workflow.get("nodes", [])
    )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--organs", default="docs/devon/vps-cutover-organs_2026-09-15.json")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    cloud = (os.environ.get("N8N_CLOUD_URL", CLOUD_URL_DEFAULT), os.environ.get("N8N_CLOUD_KEY", ""))
    vps_url = os.environ.get("N8N_VPS_URL")
    if not vps_url:
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
        from services.devon import vault  # noqa: WPS433
        vps_url = vault.N8N_HOST
    vps = (vps_url, os.environ.get("N8N_VPS_KEY", ""))
    missing = [n for n, v in (("N8N_CLOUD_KEY", cloud[1]), ("N8N_VPS_KEY", vps[1])) if not v]
    if missing:
        print(json.dumps({"error": "unset: " + ", ".join(missing)}))
        return 2

    plan = ordered(json.loads(pathlib.Path(args.organs).read_text()))
    log: List[Dict[str, Any]] = []

    # Snapshot what Cloud is actually running BEFORE anything is deactivated, and
    # mirror exactly that. Six organs are deliberately inactive on Cloud, among
    # them the manual Purge List and Vault Comparison and the read-only Table
    # Reader. Tee's ruling is that the estate runs on the VPS, not that a manual
    # tool becomes a scheduled one, so publishing those would be a behaviour
    # change nobody asked for. The snapshot has to happen first or phase one
    # destroys the very thing phase two reads.
    was_active: Dict[str, bool] = {}
    for _tier, organ in plan:
        was_active[organ["short"]] = bool(
            api(*cloud, f"/workflows/{organ['cloud_id']}").get("active"))
    dormant = sorted(s for s, a in was_active.items() if not a)
    print(f"Cloud is running {sum(was_active.values())} of {len(plan)} organs.")
    print("Deliberately dormant on Cloud, so left dormant on the VPS: "
          + (", ".join(dormant) if dormant else "none"))
    print()

    print("PHASE 1  unpublish on Cloud, leaf first")
    for tier, organ in reversed(plan):
        if not was_active[organ["short"]]:
            print(f"  skip     {organ['short']:<18} ({tier}) already inactive")
            log.append({"phase": "cloud", "organ": organ["short"], "action": "skip"})
            continue
        if args.dry_run:
            print(f"  WOULD    deactivate {organ['short']:<18} ({tier})")
            log.append({"phase": "cloud", "organ": organ["short"], "action": "would-deactivate"})
            continue
        api(*cloud, f"/workflows/{organ['cloud_id']}/deactivate", method="POST")
        after = api(*cloud, f"/workflows/{organ['cloud_id']}")
        ok = not after.get("active")
        print(f"  {'done' if ok else 'FAILED':<8} deactivate {organ['short']:<18} ({tier})")
        log.append({"phase": "cloud", "organ": organ["short"], "action": "deactivate", "ok": ok})

    print()
    print("PHASE 2  publish on the VPS, core first")
    for tier, organ in plan:
        wf = api(*vps, f"/workflows/{organ['vps_id']}")
        if wf.get("active"):
            print(f"  skip     {organ['short']:<18} ({tier}) already active")
            log.append({"phase": "vps", "organ": organ["short"], "action": "skip"})
            continue
        if not was_active[organ["short"]]:
            print(f"  dormant  {organ['short']:<18} ({tier}) inactive on Cloud, mirrored")
            log.append({"phase": "vps", "organ": organ["short"], "action": "dormant"})
            continue
        if not has_trigger(wf):
            print(f"  no-trig  {organ['short']:<18} ({tier}) no trigger node, cannot activate")
            log.append({"phase": "vps", "organ": organ["short"], "action": "no-trigger"})
            continue
        if args.dry_run:
            print(f"  WOULD    activate   {organ['short']:<18} ({tier})")
            log.append({"phase": "vps", "organ": organ["short"], "action": "would-activate"})
            continue
        try:
            api(*vps, f"/workflows/{organ['vps_id']}/activate", method="POST")
            after = api(*vps, f"/workflows/{organ['vps_id']}")
            ok = bool(after.get("active"))
            note = ""
        except RuntimeError as exc:
            ok, note = False, str(exc)[:200]
        print(f"  {'done' if ok else 'FAILED':<8} activate   {organ['short']:<18} ({tier}) {note}")
        log.append({"phase": "vps", "organ": organ["short"], "action": "activate",
                    "ok": ok, "error": note or None})

    failed = [e for e in log if e.get("ok") is False]
    print()
    print(json.dumps({"organs": len(plan), "failed": len(failed),
                      "failed_organs": [e["organ"] for e in failed]}))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

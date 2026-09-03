#!/usr/bin/env python3
"""Reconcile the estate's records against the live estate they describe.

The standing failure class of this system: an artifact is written, reality
moves, and nothing writes back. Between 2026-08-23 and 2026-09-01 that class
produced three stale records, each corrected only after a session tripped
over it. `vault.py` carried `devon-capture` as unauthenticated for eight days
after header auth went live. The same file called the approval-request
entropy fix pending for six days after the live workflow shipped it. The
ecosystem spec said Railway autodeploy was disabled for days after pushes to
`main` started deploying themselves. The first run of this tool found two
more: the Heartbeat and the Error Alarm recorded active while the live
instance held them inactive.

This tool makes that class fail loudly. The records make claims, the live
estate is the authority, and a run fails when they disagree:

    snapshot   read the live surfaces, write an observations JSON file
    check      compare every claim against observations, exit nonzero on drift

Claims come from two places. `services/devon/vault.py` is imported (it is
data only, importing it performs no effect) and every webhook auth mode,
workflow state and the instance host become claims. Documents cannot be
imported, so `DOC_CLAIMS` pins each checkable sentence by quote: while the
quote is present in its doc the claim is checked, and once the doc is
amended the claim retires itself and stays pinned as a tripwire, so a later
edit that resurrects the corrected sentence is caught on the next run.

Live reads, all optional and all read only:

    N8N_SOURCE_URL / N8N_SOURCE_KEY   the n8n instance, same env as
                                      scripts/n8n_migrate.py. The key needs
                                      workflow:list and workflow:read. The
                                      URL defaults to vault.N8N_HOST.
    RAILWAY_API_TOKEN                 Railway GraphQL, deployment reads only.
    RECONCILE_MAIN_HEAD               the sha `main` points at, for the
                                      autodeploy checks. Defaults to
                                      `git rev-parse origin/main`.

A source with no key is reported UNVERIFIED, never silently passed, and
`--strict` turns UNVERIFIED into failure for scheduled runs that are supposed
to hold keys. `check --observations file.json` runs against a saved snapshot
instead of the network, which is also how the tests exercise every path.

What this cannot check, stated plainly: prose rulings. A sentence like the
old "fix still pending" in an `open_ruling` has no machine readable shadow,
so every run ends by listing the open rulings only a human can retire.
Enumerated every run, they cannot rot silently.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys
import textwrap
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

TIMEOUT = 60

OK = "OK"
DRIFT = "DRIFT"
UNVERIFIED = "UNVERIFIED"
RETIRED = "RETIRED"

# devon-api on Railway, ids read from the live service on 2026-09-01. These
# are lookup addresses, not claims: nothing fails when they change, reads
# just start failing until the env overrides point at the right service.
RAILWAY_GRAPHQL = "https://backboard.railway.com/graphql/v2"
RAILWAY_PROJECT = "3bf31602-1e72-4fac-ade7-4c89106d8896"
RAILWAY_SERVICE = "c8e24427-74bd-4b71-85c8-d9b9bd496cf4"


class ApiError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Claims, the pure half
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Claim:
    """One checkable statement a record makes about the live estate."""

    record: str  # where the claim is written, e.g. vault.WEBHOOKS['devon-capture']
    subject: str  # what the claim is about, for a human reading the report
    verifier: str  # which checker settles it
    expected: Any  # what the record says should be true


@dataclass(frozen=True)
class Finding:
    claim: Claim
    status: str
    detail: str


# How the vault phrases an auth mode, against what the live webhook node
# carries in its `authentication` parameter. The approve-decide token is
# enforced inside the workflow, so its node correctly carries none.
_AUTH_PREFIXES: Tuple[Tuple[str, str], ...] = (
    ("header", "headerAuth"),
    ("basic", "basicAuth"),
    ("jwt", "jwtAuth"),
    ("single use token", "none"),
    ("none", "none"),
)


def node_auth_for(vault_auth: Optional[str]) -> str:
    """The live node auth value a vault auth phrase claims."""
    if vault_auth is None:
        return "none"
    lowered = vault_auth.lower()
    for prefix, node_auth in _AUTH_PREFIXES:
        if lowered.startswith(prefix):
            return node_auth
    raise ValueError(
        f"unmapped vault auth phrase {vault_auth!r}. Extend _AUTH_PREFIXES rather "
        "than skipping the entry: an unparseable claim is an unchecked claim."
    )


_STATE_PREFIXES: Tuple[Tuple[str, str], ...] = (
    ("active", "active"),
    ("inactive", "inactive"),
    ("retired", "retired"),
    # A manual workflow has no trigger to switch on, the instance holds it inactive.
    ("manual", "inactive"),
)


def workflow_state_for(vault_state: str) -> str:
    """The live active state a vault state phrase claims: active, inactive or retired."""
    lowered = vault_state.lower()
    for prefix, state in _STATE_PREFIXES:
        if lowered.startswith(prefix):
            return state
    raise ValueError(
        f"unmapped vault state phrase {vault_state!r}. Extend _STATE_PREFIXES rather "
        "than skipping the entry: an unparseable claim is an unchecked claim."
    )


def vault_claims(
    webhooks: Optional[Dict[str, Dict[str, Any]]] = None,
    workflows: Optional[Dict[str, Dict[str, str]]] = None,
    host: Optional[str] = None,
) -> List[Claim]:
    """Every mechanically checkable claim the vault map makes about n8n.

    The defaults read the real vault module. Tests pass synthetic maps, which
    is how the regression pins for the stale entries of 2026-08-31 stay
    runnable after the real entries were corrected.
    """
    from services.devon import vault

    webhooks = vault.WEBHOOKS if webhooks is None else webhooks
    workflows = vault.WORKFLOWS if workflows is None else workflows
    host = vault.N8N_HOST if host is None else host

    claims = [Claim("vault.N8N_HOST", "the n8n instance host", "n8n_host", host)]
    for path in sorted(webhooks):
        entry = webhooks[path]
        claims.append(
            Claim(
                record=f"vault.WEBHOOKS[{path!r}]",
                subject=f"webhook {path} on workflow {entry['workflow']}",
                verifier="webhook_auth",
                expected={
                    "workflow": entry["workflow"],
                    "path": path,
                    "auth": node_auth_for(entry["auth"]),
                },
            )
        )
    for name in sorted(workflows):
        entry = workflows[name]
        claims.append(
            Claim(
                record=f"vault.WORKFLOWS[{name!r}]",
                subject=f"workflow {name} ({entry['id']})",
                verifier="workflow_state",
                expected={"id": entry["id"], "state": workflow_state_for(entry["state"])},
            )
        )
    return claims


# Document claims, pinned by quote. While the quote is present in its doc the
# claim is checked. Once the doc is amended the quote disappears and the claim
# reports RETIRED, staying pinned so a later edit that resurrects the old
# sentence revives the check and fails it.
DOC_CLAIMS: Tuple[Dict[str, Any], ...] = (
    {
        # Stale from some point before 2026-08-31, corrected 2026-09-01.
        # Kept as a tripwire: this sentence must never come back unverified.
        "doc": "docs/devon/SYS_SPEC_devon-ecosystem_v1_2026-08-26.md",
        "quote": "autodeploy is disabled",
        "verifier": "railway_autodeploy_off",
        "expected": None,
    },
    {
        # The standing claim that replaced it.
        "doc": "docs/devon/SYS_SPEC_devon-ecosystem_v1_2026-08-26.md",
        "quote": "deployed without hands",
        "verifier": "railway_autodeploy_on",
        "expected": None,
    },
    {
        # The migration pre-flight inventory. Holds until cutover changes the
        # Cloud estate, at which point the doc must be amended, dated.
        "doc": "docs/devon/SYS_OPS_n8n-cloud-to-vps-migration_v1_2026-08-31.md",
        "quote": "the 58 workflows",
        "verifier": "n8n_total",
        "expected": {"total": 58},
    },
    # Records the DEVON and Hermes audit of 2026-09-02 (item 14) found stale
    # and corrected, dated. Each retired sentence stays pinned as a tripwire:
    # a later edit that brings it back reports DRIFT, and the standing
    # sentence that replaced it is checked against the repository.
    {
        "doc": "FLAGSHIP.md",
        "quote": "production SHA is still d2aff6d",
        "verifier": "superseded",
        "expected": {"by": "57fdddb, the PR #111 merge", "dated": "2026-09-02"},
    },
    {
        "doc": "COMPLETION.md",
        "quote": "still production SHA d2aff6d",
        "verifier": "superseded",
        "expected": {"by": "57fdddb, the PR #111 merge", "dated": "2026-09-02"},
    },
    {
        "doc": "docs/GAUNTLET.md",
        "quote": "still d2aff6d",
        "verifier": "superseded",
        "expected": {"by": "57fdddb, the PR #111 merge", "dated": "2026-09-02"},
    },
    {
        "doc": "docs/GAUNTLET.md",
        "quote": "still SHA d2aff6d",
        "verifier": "superseded",
        "expected": {"by": "57fdddb, the PR #111 merge", "dated": "2026-09-02"},
    },
    {
        "doc": "DEPLOY.md",
        "quote": "| meta-supreme-web |",
        "verifier": "superseded",
        "expected": {"by": "meta-supreme-apex-genesis-web", "dated": "2026-09-02"},
    },
    {
        # The Hermes v2 status said head 010 while production ran 013, then 015.
        "doc": "docs/devon/SYS_OPS_devon-hermes-stack-status_v2_2026-08-25.md",
        "quote": "Alembic head 010",
        "verifier": "superseded",
        "expected": {"by": "Alembic head 015, dated 2026-09-02", "dated": "2026-09-02"},
    },
    {
        # 015 stood on 2026-09-02 and was superseded on 2026-09-03, once the
        # deployment carrying 017 and 018 landed. The retired sentence coming
        # back is drift, the same as the 010 above it.
        "doc": "docs/devon/SYS_OPS_devon-hermes-stack-status_v2_2026-08-25.md",
        "quote": "Alembic head 015 as of",
        "verifier": "superseded",
        "expected": {"by": "Alembic head 018, dated 2026-09-03", "dated": "2026-09-03"},
    },
    {
        # The standing head, checked against what is deployed: the migrations
        # directory at the commit of the newest successful Railway deployment
        # (Dockerfile.api runs alembic upgrade head before the API takes
        # traffic). Without a Railway read this is UNVERIFIED; the source
        # tree alone says what the next deploy will apply, not what is deployed.
        "doc": "docs/devon/SYS_OPS_devon-hermes-stack-status_v2_2026-08-25.md",
        "quote": "Alembic head 018",
        "verifier": "alembic_head",
        "expected": {"head": "018"},
    },
    {
        # The cron line named a module that never existed in the root package.
        "doc": "OPERATING.md",
        "quote": "python -m app.cli.dispatch",
        "verifier": "repo_file",
        "expected": {"path": "app/cli/dispatch.py", "present": True},
    },
    {
        "doc": "RUNBOOK.md",
        "quote": "python -m app.cli.dispatch",
        "verifier": "repo_file",
        "expected": {"path": "app/cli/dispatch.py", "present": True},
    },
    {
        "doc": "OPERATING.md",
        "quote": "python dispatch.py",
        "verifier": "repo_file",
        "expected": {"path": "dispatch.py", "present": True},
    },
    {
        "doc": "RUNBOOK.md",
        "quote": "python dispatch.py",
        "verifier": "repo_file",
        "expected": {"path": "dispatch.py", "present": True},
    },
    {
        # The cron line runs inside the API image, so the image must ship the
        # entrypoint; a file in the checkout that the Dockerfile does not copy
        # is a command that exits before dispatching.
        "doc": "OPERATING.md",
        "quote": "python dispatch.py",
        "verifier": "image_file",
        "expected": {"path": "dispatch.py", "image": "infrastructure/docker/Dockerfile.api"},
    },
    {
        "doc": "RUNBOOK.md",
        "quote": "python dispatch.py",
        "verifier": "image_file",
        "expected": {"path": "dispatch.py", "image": "infrastructure/docker/Dockerfile.api"},
    },
)


def doc_claims(doc_texts: Dict[str, str]) -> List[Claim]:
    """Claims pinned to document sentences. `doc_texts` maps repo path to content.

    A doc that is present without the quote retired its claim by amendment.
    A doc that is missing entirely is different: nothing was amended, the
    record the registry points at is gone, and treating that as retirement
    would let a deleted or renamed doc silently drop every tripwire in it.
    """
    claims = []
    for pinned in DOC_CLAIMS:
        text = doc_texts.get(pinned["doc"])
        if text is None:
            verifier = "doc_missing"
        elif pinned["quote"] in text:
            verifier = pinned["verifier"]
        else:
            verifier = "quote_retired"
        claims.append(
            Claim(
                record=f"{pinned['doc']} ({pinned['quote']!r})",
                subject=pinned["quote"],
                verifier=verifier,
                expected=pinned["expected"],
            )
        )
    return claims


def open_rulings(
    webhooks: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[Tuple[str, str]]:
    """Every prose ruling in the vault. Human judgement only, listed every run."""
    from services.devon import vault

    webhooks = vault.WEBHOOKS if webhooks is None else webhooks
    return [
        (f"vault.WEBHOOKS[{path!r}]", webhooks[path]["open_ruling"])
        for path in sorted(webhooks)
        if webhooks[path].get("open_ruling")
    ]


# ---------------------------------------------------------------------------
# Checkers, pure claim against observations
# ---------------------------------------------------------------------------


def _n8n_or_none(observations: Dict[str, Any], needs: str) -> Tuple[Optional[Dict], str]:
    n8n = observations.get("n8n") or {}
    if n8n.get("error"):
        return None, str(n8n["error"])
    if needs not in n8n:
        return None, "no n8n observation was captured"
    return n8n, ""


def _check_n8n_host(claim: Claim, observations: Dict[str, Any]) -> Tuple[str, str]:
    n8n, why = _n8n_or_none(observations, "host")
    if n8n is None:
        return UNVERIFIED, why
    live = str(n8n["host"]).rstrip("/")
    if live == str(claim.expected).rstrip("/"):
        if n8n.get("host_source") == "vault_default":
            # The read defaulted to the vault's own value, so agreement is an
            # echo, not evidence. The fetch succeeding there does prove the
            # host serves an n8n API that accepts the key, and nothing more.
            return UNVERIFIED, (
                f"the read used the vault's own host value ({live}) because "
                "N8N_SOURCE_URL is unset. The key worked there, but only an "
                "independently configured URL makes this claim falsifiable."
            )
        return OK, live
    return DRIFT, f"the vault records {claim.expected}, the live read used {live}"


def _check_webhook_auth(claim: Claim, observations: Dict[str, Any]) -> Tuple[str, str]:
    n8n, why = _n8n_or_none(observations, "webhooks")
    if n8n is None:
        return UNVERIFIED, why
    expected = claim.expected
    nodes = (n8n.get("webhooks") or {}).get(expected["workflow"])
    if nodes is None:
        return DRIFT, f"workflow {expected['workflow']} was not found on the instance"
    for node in nodes:
        if node.get("path") == expected["path"]:
            live = node.get("auth") or "none"
            if live == expected["auth"]:
                return OK, f"the live node carries {live}"
            return DRIFT, (
                f"the vault records {expected['auth']}, the live node carries {live}"
            )
    return DRIFT, (
        f"no webhook node with path {expected['path']} on workflow {expected['workflow']}"
    )


def _check_workflow_state(claim: Claim, observations: Dict[str, Any]) -> Tuple[str, str]:
    n8n, why = _n8n_or_none(observations, "workflows")
    if n8n is None:
        return UNVERIFIED, why
    live = n8n["workflows"].get(claim.expected["id"])
    want = claim.expected["state"]
    if live is None:
        if want == "retired":
            return OK, "absent from the instance, consistent with retirement"
        return DRIFT, f"recorded {want} but absent from the instance"
    if bool(live.get("active")):
        if want == "active":
            return OK, "active"
        return DRIFT, f"recorded {want} but the live workflow is active"
    if want == "active":
        return DRIFT, "recorded active but the live workflow is inactive"
    return OK, "inactive"


def _head_deployment(
    observations: Dict[str, Any],
) -> Tuple[Optional[Dict[str, Any]], bool, str]:
    """The recent Railway deployment on the main head, if any.

    Returns (deployment, knowable, detail): deployment is the matching entry
    or None, knowable is False when the question cannot be answered at all
    (no reads, no head), and detail says why or names what matched.
    """
    railway = observations.get("railway") or {}
    if railway.get("error"):
        return None, False, str(railway["error"])
    deployments = railway.get("deployments")
    if not deployments:
        return None, False, "no Railway deployments were captured"
    head = (observations.get("repo") or {}).get("main_head") or ""
    if not head:
        return None, False, "the main head is unknown, set RECONCILE_MAIN_HEAD"
    for deployment in deployments:
        sha = str(deployment.get("commit_sha") or "")
        if sha and (sha.startswith(head) or head.startswith(sha)):
            status = deployment.get("status", "?")
            detail = f"deployment {deployment.get('id', '?')} ({status}) is on {sha[:12]}"
            return deployment, True, detail
    return None, True, f"none of the {len(deployments)} recent deployments sit on {head[:12]}"


def _check_railway_autodeploy_off(
    claim: Claim, observations: Dict[str, Any]
) -> Tuple[str, str]:
    deployment, knowable, detail = _head_deployment(observations)
    if not knowable:
        return UNVERIFIED, detail
    if deployment is not None:
        # Any deployment on the head contradicts "no push triggers a build",
        # whatever became of the build afterwards.
        return DRIFT, (
            "the doc says every merge needs a manual deployment, but " + detail + ". "
            "Either autodeploy is on or someone deployed by hand without recording "
            "it. Both mean the doc must be corrected, dated."
        )
    return UNVERIFIED, (
        detail + ". The claim cannot be confirmed from a lagging surface, read the "
        "Railway dashboard back by hand."
    )


def _check_railway_autodeploy_on(
    claim: Claim, observations: Dict[str, Any]
) -> Tuple[str, str]:
    deployment, knowable, detail = _head_deployment(observations)
    if not knowable:
        return UNVERIFIED, detail
    if deployment is not None:
        # "Deployed without hands" needs the build to have actually landed. A
        # failed or crashed attempt proves the trigger fired and nothing more.
        if deployment.get("status") == "SUCCESS":
            return OK, detail
        return UNVERIFIED, (
            detail + ". A deployment triggered from the head but did not succeed, "
            "read the build back by hand before trusting the surface."
        )
    return UNVERIFIED, (
        detail + ". Either main just moved or autodeploy broke again, read the "
        "deployment back by hand before trusting either."
    )


def _check_n8n_total(claim: Claim, observations: Dict[str, Any]) -> Tuple[str, str]:
    n8n, why = _n8n_or_none(observations, "workflows")
    if n8n is None:
        return UNVERIFIED, why
    total = len(n8n["workflows"])
    if total == claim.expected["total"]:
        return OK, f"{total} workflows on the instance"
    return DRIFT, (
        f"the doc records {claim.expected['total']} workflows, the instance holds "
        f"{total}. Amend the doc, dated, or explain the change there."
    )


def _check_quote_retired(claim: Claim, observations: Dict[str, Any]) -> Tuple[str, str]:
    return RETIRED, "the quote is no longer in the doc, the claim retired itself"


def _check_doc_missing(claim: Claim, observations: Dict[str, Any]) -> Tuple[str, str]:
    return DRIFT, (
        "the pinned doc does not exist. A deleted or renamed doc is not an "
        "amendment: move the pin with the doc, or record why the doc is gone."
    )


def _check_superseded(claim: Claim, observations: Dict[str, Any]) -> Tuple[str, str]:
    """A sentence retired by a dated correction is back in its doc."""
    expected = claim.expected or {}
    return DRIFT, (
        f"this sentence was retired on {expected.get('dated', 'an earlier date')}, "
        f"superseded by {expected.get('by', 'a dated correction')}, and it came "
        "back. Amend it, dated, or record there why the old fact returned."
    )


def _check_alembic_head(claim: Claim, observations: Dict[str, Any]) -> Tuple[str, str]:
    """The doc describes the deployed database, so the evidence is the
    migrations directory at the commit of the newest successful Railway
    deployment, never the source tree of this checkout."""
    repo = observations.get("repo") or {}
    deployed = repo.get("deployed_alembic_head")
    if not deployed:
        reason = repo.get("deployed_reason") or (
            "no successful Railway deployment was read (RAILWAY_API_TOKEN unset, "
            "or the read failed)"
        )
        return UNVERIFIED, (
            f"the deployed head is unknown: {reason}. The source tree heads at "
            f"{repo.get('alembic_head') or 'unknown'}, which says what the next "
            "deploy will apply, not what is deployed."
        )
    where = (
        f"Railway deployment {repo.get('deployed_deployment') or 'unknown'} at commit "
        f"{str(repo.get('deployed_commit') or '')[:12]}"
    )
    if deployed == claim.expected["head"]:
        return OK, (
            f"{where} carries migrations up to {deployed}, applied by alembic upgrade "
            "head before it took traffic, as the doc records"
        )
    return DRIFT, (
        f"the doc records Alembic head {claim.expected['head']}; {where} carries "
        f"migrations up to {deployed}. Amend the doc, dated."
    )


def _check_image_file(claim: Claim, observations: Dict[str, Any]) -> Tuple[str, str]:
    images = (observations.get("repo") or {}).get("image_files") or {}
    image, path = claim.expected["image"], claim.expected["path"]
    shipped = (images.get(image) or {}).get(path)
    if shipped is None:
        return UNVERIFIED, f"{image} was not read for {path}"
    if shipped:
        return OK, f"{image} copies {path} into the image, so the documented command exists where it runs"
    return DRIFT, (
        f"the doc's command needs {path}, which {image} does not copy into the image. "
        "Ship it or amend the doc, dated."
    )


def _check_repo_file(claim: Claim, observations: Dict[str, Any]) -> Tuple[str, str]:
    files = (observations.get("repo") or {}).get("files") or {}
    path = claim.expected["path"]
    if path not in files:
        return UNVERIFIED, f"the repository was not read for {path}"
    if files[path] == claim.expected["present"]:
        state = "exists" if files[path] else "is absent"
        return OK, f"{path} {state}, as the doc records"
    state = "does not exist" if claim.expected["present"] else "exists"
    return DRIFT, (
        f"the doc names {path}, which {state} in the repository. Amend the doc, dated."
    )


CHECKERS = {
    "n8n_host": _check_n8n_host,
    "webhook_auth": _check_webhook_auth,
    "workflow_state": _check_workflow_state,
    "railway_autodeploy_off": _check_railway_autodeploy_off,
    "railway_autodeploy_on": _check_railway_autodeploy_on,
    "n8n_total": _check_n8n_total,
    "quote_retired": _check_quote_retired,
    "doc_missing": _check_doc_missing,
    "superseded": _check_superseded,
    "alembic_head": _check_alembic_head,
    "repo_file": _check_repo_file,
    "image_file": _check_image_file,
}


def check(claims: Sequence[Claim], observations: Dict[str, Any]) -> List[Finding]:
    findings = []
    for claim in claims:
        status, detail = CHECKERS[claim.verifier](claim, observations)
        findings.append(Finding(claim=claim, status=status, detail=detail))
    return findings


def exit_code(findings: Sequence[Finding], strict: bool = False) -> int:
    statuses = {finding.status for finding in findings}
    if DRIFT in statuses:
        return 1
    if strict and UNVERIFIED in statuses:
        return 1
    return 0


_STATUS_ORDER = {DRIFT: 0, UNVERIFIED: 1, RETIRED: 2, OK: 3}


def render(findings: Sequence[Finding], rulings: Sequence[Tuple[str, str]]) -> str:
    lines = []
    ordered = sorted(findings, key=lambda f: (_STATUS_ORDER[f.status], f.claim.record))
    for finding in ordered:
        lines.append(f"{finding.status:10} {finding.claim.record}: {finding.detail}")
    counts = Counter(finding.status for finding in findings)
    summary = ", ".join(
        f"{counts[status]} {status.lower()}"
        for status in (DRIFT, UNVERIFIED, RETIRED, OK)
        if counts[status]
    )
    lines.append("")
    lines.append(f"{len(findings)} claims: {summary}")
    if rulings:
        lines.append("")
        lines.append("Open rulings, human judgement only, listed so they cannot rot silently:")
        for record, ruling in rulings:
            lines.append(f"  {record}:")
            lines.extend(
                textwrap.wrap(ruling, width=74, initial_indent="    ", subsequent_indent="    ")
            )
    lines.append("")
    if counts[DRIFT]:
        lines.append(
            "DRIFT: a record disagrees with the live estate. Correct the record or "
            "the estate, dated, today. A record left wrong is the failure class "
            "this tool exists to stop."
        )
    else:
        lines.append("No drift in the checkable claims.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Live reads, the effectful half. Read only, every one.
# ---------------------------------------------------------------------------


def _request(
    url: str,
    headers: Dict[str, str],
    payload: Optional[Dict[str, Any]] = None,
) -> Any:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    for name, value in headers.items():
        req.add_header(name, value)
    req.add_header("Accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            body = response.read().decode()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:400]
        raise ApiError(f"{url} returned HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise ApiError(f"{url} was unreachable: {exc.reason}") from exc
    except (TimeoutError, OSError) as exc:
        # A timeout mid-read arrives as the bare socket error, not URLError.
        raise ApiError(f"{url} died mid-read: {exc}") from exc
    if not body:
        return {}
    try:
        return json.loads(body)
    except ValueError as exc:
        raise ApiError(f"{url} returned a non-JSON body: {body[:200]!r}") from exc


def _paged_workflows(base: str, key: str) -> Iterator[Dict[str, Any]]:
    cursor = None
    while True:
        query = "?limit=100" + (f"&cursor={cursor}" if cursor else "")
        page = _request(
            f"{base.rstrip('/')}/api/v1/workflows{query}", {"X-N8N-API-KEY": key}
        )
        for workflow in page.get("data", []):
            yield workflow
        cursor = page.get("nextCursor")
        if not cursor:
            return


def webhook_nodes(workflow_detail: Dict[str, Any]) -> List[Dict[str, str]]:
    """The live webhook trigger nodes of one workflow detail read.

    Disabled nodes are skipped: a disabled webhook serves nothing, and
    letting one shadow the enabled node on the same path would verify the
    wrong auth mode.
    """
    nodes = []
    for node in workflow_detail.get("nodes", []):
        if node.get("type") != "n8n-nodes-base.webhook" or node.get("disabled"):
            continue
        parameters = node.get("parameters") or {}
        nodes.append(
            {
                "path": parameters.get("path", ""),
                "auth": parameters.get("authentication") or "none",
                "method": parameters.get("httpMethod", "GET"),
            }
        )
    return nodes


def fetch_n8n(base: str, key: str, detail_ids: Sequence[str]) -> Dict[str, Any]:
    """Workflow census plus the webhook nodes of the claimed workflows."""
    workflows: Dict[str, Dict[str, Any]] = {}
    for workflow in _paged_workflows(base, key):
        workflows[workflow["id"]] = {
            "name": workflow.get("name", ""),
            "active": bool(workflow.get("active")),
        }
    webhooks: Dict[str, List[Dict[str, str]]] = {}
    for workflow_id in sorted(set(detail_ids)):
        if workflow_id not in workflows:
            continue  # absence is the state checker's finding, not a fetch error
        detail = _request(
            f"{base.rstrip('/')}/api/v1/workflows/{workflow_id}",
            {"X-N8N-API-KEY": key},
        )
        webhooks[workflow_id] = webhook_nodes(detail)
    return {"host": base.rstrip("/"), "workflows": workflows, "webhooks": webhooks}


def fetch_railway(
    token: str,
    project: Optional[str] = None,
    service: Optional[str] = None,
    environment: Optional[str] = None,
) -> Dict[str, Any]:
    """The five most recent deployments of the API service, newest first.

    Without an environment id the window spans every environment of the
    service, so PR environments could dilute it. Set RAILWAY_ENVIRONMENT_ID
    to pin the read to production once that id is worth recording.
    """
    environment = environment or os.environ.get("RAILWAY_ENVIRONMENT_ID")
    variables: Dict[str, Any] = {
        "projectId": project or RAILWAY_PROJECT,
        "serviceId": service or RAILWAY_SERVICE,
    }
    input_fields = "projectId: $projectId, serviceId: $serviceId"
    declarations = "$projectId: String!, $serviceId: String!"
    if environment:
        variables["environmentId"] = environment
        input_fields += ", environmentId: $environmentId"
        declarations += ", $environmentId: String!"
    query = (
        f"query ({declarations}) {{"
        f" deployments(first: 5, input: {{{input_fields}}})"
        " { edges { node { id status createdAt meta } } } }"
    )
    body = _request(
        RAILWAY_GRAPHQL,
        {"Authorization": f"Bearer {token}"},
        {"query": query, "variables": variables},
    )
    if body.get("errors"):
        raise ApiError(f"Railway GraphQL: {body['errors'][0].get('message', body['errors'][0])}")
    deployments = []
    for edge in body.get("data", {}).get("deployments", {}).get("edges", []):
        node = edge.get("node") or {}
        meta = node.get("meta") or {}
        deployments.append(
            {
                "id": node.get("id", ""),
                "status": node.get("status", ""),
                "created_at": node.get("createdAt", ""),
                "commit_sha": meta.get("commitHash") or meta.get("commitSha") or "",
            }
        )
    return {"deployments": deployments}


def _main_head() -> Optional[str]:
    override = os.environ.get("RECONCILE_MAIN_HEAD")
    if override:
        return override.strip()
    for ref in ("origin/main", "HEAD"):
        try:
            result = subprocess.run(
                ["git", "rev-parse", ref],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except OSError:
            return None
        if result.returncode == 0:
            return result.stdout.strip()
    return None


def _alembic_head(root: pathlib.Path = REPO_ROOT) -> Optional[str]:
    """The highest numbered revision file under database/migrations/versions,
    the head CI asserts and the docs quote."""
    versions = pathlib.Path(root) / "database" / "migrations" / "versions"
    if not versions.is_dir():
        return None
    numbers = sorted(path.name[:3] for path in versions.glob("[0-9][0-9][0-9]_*.py"))
    return numbers[-1] if numbers else None


def _image_copies(root: pathlib.Path = REPO_ROOT, image: str = "infrastructure/docker/Dockerfile.api") -> List[str]:
    """The source paths a Dockerfile's COPY lines put into the image."""
    path = pathlib.Path(root) / image
    if not path.exists():
        return []
    sources: List[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0].upper() == "COPY":
            sources.extend(
                part.lstrip("./").rstrip("/") for part in parts[1:-1] if not part.startswith("--")
            )
    return sources


def _pinned_image_files(root: pathlib.Path = REPO_ROOT) -> Dict[str, Dict[str, bool]]:
    """Whether each image a doc claim names ships the path the claim needs."""
    shipped: Dict[str, Dict[str, bool]] = {}
    for pinned in DOC_CLAIMS:
        if pinned["verifier"] != "image_file":
            continue
        image, path = pinned["expected"]["image"], pinned["expected"]["path"]
        copies = _image_copies(root, image)
        shipped.setdefault(image, {})[path] = any(
            path == src or path.startswith(src + "/") for src in copies
        )
    return shipped


def _deployed_alembic_head(railway: Dict[str, Any], root: pathlib.Path = REPO_ROOT) -> Dict[str, Any]:
    """The migrations head at the commit of the newest successful Railway
    deployment. Dockerfile.api runs alembic upgrade head before the API takes
    traffic, so a SUCCESS deployment's commit says what the deployed database
    is at; the source tree only says what the next deploy will apply."""
    deployments = (railway or {}).get("deployments") or []
    newest = next(
        (d for d in deployments if d.get("status") == "SUCCESS" and d.get("commit_sha")), None
    )
    if newest is None:
        return {}
    sha = str(newest["commit_sha"])
    found: Dict[str, Any] = {"deployed_commit": sha, "deployed_deployment": newest.get("id", "")}
    try:
        result = subprocess.run(
            ["git", "ls-tree", "--name-only", sha, "database/migrations/versions/"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except OSError:
        return {**found, "deployed_alembic_head": None, "deployed_reason": "git is unavailable"}
    if result.returncode != 0:
        return {
            **found,
            "deployed_alembic_head": None,
            "deployed_reason": f"commit {sha[:12]} is not in this clone; fetch main and rerun",
        }
    names = [line.rsplit("/", 1)[-1] for line in result.stdout.splitlines()]
    numbers = sorted(name[:3] for name in names if re.match(r"^\d{3}_.*\.py$", name))
    return {**found, "deployed_alembic_head": numbers[-1] if numbers else None}


def _pinned_files_present(root: pathlib.Path = REPO_ROOT) -> Dict[str, bool]:
    """Presence of every repository path a doc claim names."""
    paths = {
        pinned["expected"]["path"]
        for pinned in DOC_CLAIMS
        if pinned["verifier"] == "repo_file"
    }
    return {path: (pathlib.Path(root) / path).exists() for path in sorted(paths)}


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def gather_observations() -> Dict[str, Any]:
    from services.devon import vault

    observations: Dict[str, Any] = {"read_at": _now_iso()}

    env_base = os.environ.get("N8N_SOURCE_URL")
    base = env_base or vault.N8N_HOST
    key = os.environ.get("N8N_SOURCE_KEY")
    if key:
        detail_ids = [entry["workflow"] for entry in vault.WEBHOOKS.values()]
        try:
            observations["n8n"] = fetch_n8n(base, key, detail_ids)
            observations["n8n"]["host_source"] = "env" if env_base else "vault_default"
        except ApiError as exc:
            observations["n8n"] = {"error": str(exc)}
    else:
        observations["n8n"] = {"error": "N8N_SOURCE_KEY is not set"}

    token = os.environ.get("RAILWAY_API_TOKEN")
    if token:
        try:
            observations["railway"] = fetch_railway(token)
        except ApiError as exc:
            observations["railway"] = {"error": str(exc)}
    else:
        observations["railway"] = {"error": "RAILWAY_API_TOKEN is not set"}

    head = _main_head()
    observations["repo"] = {"main_head": head} if head else {}
    observations["repo"]["alembic_head"] = _alembic_head()
    observations["repo"]["files"] = _pinned_files_present()
    observations["repo"]["image_files"] = _pinned_image_files()
    observations["repo"].update(_deployed_alembic_head(observations.get("railway") or {}))
    return observations


def _read_doc_texts(root: pathlib.Path = REPO_ROOT) -> Dict[str, str]:
    texts = {}
    for pinned in DOC_CLAIMS:
        path = pathlib.Path(root) / pinned["doc"]
        if path.exists():
            texts[pinned["doc"]] = path.read_text(encoding="utf-8")
    return texts


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)

    snapshot = commands.add_parser(
        "snapshot", help="read the live surfaces and write an observations file"
    )
    snapshot.add_argument("--out", required=True, help="path for the observations JSON")

    checker = commands.add_parser(
        "check", help="compare every claim against observations, exit 1 on drift"
    )
    checker.add_argument(
        "--observations",
        help="a saved snapshot to check against instead of reading the network",
    )
    checker.add_argument(
        "--strict",
        action="store_true",
        help="an UNVERIFIED source also fails, for runs that are supposed to hold keys",
    )

    args = parser.parse_args(argv)

    if args.command == "snapshot":
        observations = gather_observations()
        out = pathlib.Path(args.out)
        out.write_text(json.dumps(observations, indent=2, sort_keys=True) + "\n")
        print(f"wrote {out}")
        return 0

    if args.observations:
        observations = json.loads(pathlib.Path(args.observations).read_text())
    else:
        observations = gather_observations()
    claims = vault_claims() + doc_claims(_read_doc_texts())
    findings = check(claims, observations)
    print(render(findings, open_rulings()))
    return exit_code(findings, strict=args.strict)


if __name__ == "__main__":
    sys.exit(main())

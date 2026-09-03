"""Tests for the estate truth reconciler.

The load bearing tests here are the regression pins. Each stale record found
between 2026-08-31 and 2026-09-01 is rebuilt as a synthetic claim and checked
against observations shaped like the live estate was that day, so the exact
drift that went unnoticed then fails a test now:

  * `devon-capture` recorded with no auth while the live node carried
    headerAuth (stale for eight days).
  * The Heartbeat recorded active while the live instance held it inactive
    (found on the reconciler's first run, 2026-09-01).
  * The ecosystem spec claiming Railway autodeploy was disabled while pushes
    to main were deploying themselves.

The prose ruling class (the approve-request entry calling a shipped fix
pending) has no machine readable shadow. Its pin is different: the reconciler
must enumerate every open ruling on every run, so the class is at least
surfaced rather than trusted.
"""

from __future__ import annotations

import pathlib
import subprocess

import pytest

from scripts import estate_reconcile as reconcile

ROOT = pathlib.Path(__file__).parent


def _n8n_observation(workflows, webhooks):
    return {
        "n8n": {
            "host": "https://thequietoperator.app.n8n.cloud",
            "workflows": workflows,
            "webhooks": webhooks,
        }
    }


def _finding(findings, record_fragment):
    matches = [f for f in findings if record_fragment in f.claim.record]
    assert matches, f"no finding for {record_fragment!r}"
    assert len(matches) == 1, f"ambiguous record fragment {record_fragment!r}"
    return matches[0]


# ---------------------------------------------------------------------------
# The claim language
# ---------------------------------------------------------------------------


def test_vault_auth_phrases_map_to_node_auth():
    assert reconcile.node_auth_for("header x-devon-key") == "headerAuth"
    assert reconcile.node_auth_for(None) == "none"
    assert (
        reconcile.node_auth_for("single use token in the link, 72 hour expiry")
        == "none"
    )


def test_an_unmapped_auth_phrase_refuses_rather_than_skips():
    with pytest.raises(ValueError, match="unchecked claim"):
        reconcile.node_auth_for("vibes")


def test_vault_state_phrases_map_to_live_states():
    assert reconcile.workflow_state_for("active, daily 07:00") == "active"
    assert reconcile.workflow_state_for("inactive by ruling") == "inactive"
    assert reconcile.workflow_state_for("retired 2026-08-22") == "retired"
    assert reconcile.workflow_state_for("manual, read only") == "inactive"


def test_an_unmapped_state_phrase_refuses_rather_than_skips():
    with pytest.raises(ValueError, match="unchecked claim"):
        reconcile.workflow_state_for("mostly working")


def test_the_real_vault_yields_a_claim_per_entry():
    from services.devon import vault

    claims = reconcile.vault_claims()
    assert len(claims) == 1 + len(vault.WEBHOOKS) + len(vault.WORKFLOWS)
    verifiers = {claim.verifier for claim in claims}
    assert verifiers == {"n8n_host", "webhook_auth", "workflow_state"}


# ---------------------------------------------------------------------------
# Regression pin: the stale auth entry
# ---------------------------------------------------------------------------


def test_a_stale_no_auth_entry_is_caught():
    """vault carried devon-capture with auth None for eight days after header
    auth went live. This is that entry against that estate."""
    stale_webhooks = {
        "devon-capture": {"workflow": "pPIt2cELH2RVZktS", "auth": None},
    }
    claims = reconcile.vault_claims(webhooks=stale_webhooks, workflows={})
    observations = _n8n_observation(
        workflows={"pPIt2cELH2RVZktS": {"name": "Capture Webhook", "active": True}},
        webhooks={
            "pPIt2cELH2RVZktS": [
                {"path": "devon-capture", "auth": "headerAuth", "method": "POST"}
            ]
        },
    )
    finding = _finding(reconcile.check(claims, observations), "devon-capture")
    assert finding.status == reconcile.DRIFT
    assert "headerAuth" in finding.detail


def test_a_correct_auth_entry_passes():
    webhooks = {
        "devon-capture": {"workflow": "pPIt2cELH2RVZktS", "auth": "header x-devon-key"},
    }
    claims = reconcile.vault_claims(webhooks=webhooks, workflows={})
    observations = _n8n_observation(
        workflows={"pPIt2cELH2RVZktS": {"name": "Capture Webhook", "active": True}},
        webhooks={
            "pPIt2cELH2RVZktS": [
                {"path": "devon-capture", "auth": "headerAuth", "method": "POST"}
            ]
        },
    )
    finding = _finding(reconcile.check(claims, observations), "devon-capture")
    assert finding.status == reconcile.OK


def test_a_missing_webhook_path_is_drift_not_silence():
    webhooks = {
        "devon-capture": {"workflow": "pPIt2cELH2RVZktS", "auth": "header x-devon-key"},
    }
    claims = reconcile.vault_claims(webhooks=webhooks, workflows={})
    observations = _n8n_observation(
        workflows={"pPIt2cELH2RVZktS": {"name": "Capture Webhook", "active": True}},
        webhooks={"pPIt2cELH2RVZktS": []},
    )
    finding = _finding(reconcile.check(claims, observations), "devon-capture")
    assert finding.status == reconcile.DRIFT


# ---------------------------------------------------------------------------
# Regression pin: the dead pulse recorded alive
# ---------------------------------------------------------------------------


def test_a_workflow_recorded_active_but_dead_is_caught():
    """The Heartbeat was recorded active while the live instance held it
    inactive, so its six hour pulse was dead and nothing said so."""
    workflows = {"Heartbeat": {"id": "dRgTNLod2s8BAcPg", "state": "active, 6 hour pulse"}}
    claims = reconcile.vault_claims(webhooks={}, workflows=workflows)
    observations = _n8n_observation(
        workflows={"dRgTNLod2s8BAcPg": {"name": "Heartbeat", "active": False}},
        webhooks={},
    )
    finding = _finding(reconcile.check(claims, observations), "Heartbeat")
    assert finding.status == reconcile.DRIFT
    assert "inactive" in finding.detail


def test_a_retired_workflow_may_be_absent_but_not_active():
    workflows = {"Capture Hook": {"id": "Cbd24ptTPWch3aZO", "state": "retired 2026-08-22"}}
    claims = reconcile.vault_claims(webhooks={}, workflows=workflows)

    absent = reconcile.check(claims, _n8n_observation(workflows={}, webhooks={}))
    assert _finding(absent, "Capture Hook").status == reconcile.OK

    revived = reconcile.check(
        claims,
        _n8n_observation(
            workflows={"Cbd24ptTPWch3aZO": {"name": "Capture Hook", "active": True}},
            webhooks={},
        ),
    )
    assert _finding(revived, "Capture Hook").status == reconcile.DRIFT


# ---------------------------------------------------------------------------
# Regression pin: the stale deploy doctrine
# ---------------------------------------------------------------------------

SPEC_DOC = "docs/devon/SYS_SPEC_devon-ecosystem_v1_2026-08-26.md"


def test_a_stale_autodeploy_disabled_claim_is_caught():
    """The spec said autodeploy was disabled while pushes to main were
    deploying themselves. This is that sentence against that estate."""
    claims = reconcile.doc_claims({SPEC_DOC: "here autodeploy is disabled, still"})
    observations = {
        "railway": {
            "deployments": [
                {"id": "5a86779f", "status": "SUCCESS", "commit_sha": "abdc03bac97d"}
            ]
        },
        "repo": {"main_head": "abdc03bac97d83ed6175032baec7e0b1437b9c70"},
    }
    finding = _finding(reconcile.check(claims, observations), "autodeploy is disabled")
    assert finding.status == reconcile.DRIFT


def test_an_amended_doc_retires_its_claim():
    claims = reconcile.doc_claims({SPEC_DOC: "the sentence was corrected, dated"})
    findings = reconcile.check(claims, {})
    finding = _finding(findings, "autodeploy is disabled")
    assert finding.status == reconcile.RETIRED


def test_a_missing_doc_is_drift_not_retirement():
    """A deleted or renamed doc must not silently retire its tripwires."""
    findings = reconcile.check(reconcile.doc_claims({}), {})
    for finding in findings:
        assert finding.status == reconcile.DRIFT
        assert "does not exist" in finding.detail


def test_the_spec_no_longer_claims_autodeploy_is_disabled():
    """The doc correction of 2026-09-01, pinned. If the old sentence comes
    back, the reconciler starts checking it again and this test fails too."""
    text = (ROOT / SPEC_DOC).read_text(encoding="utf-8")
    assert "autodeploy is disabled" not in text
    assert "deployed without hands" in text


def test_the_standing_autodeploy_claim_never_hard_fails():
    """Autodeploy working cannot be proven from a lagging surface, so the
    standing claim reports OK or UNVERIFIED, never DRIFT."""
    claims = [c for c in reconcile.doc_claims(reconcile._read_doc_texts()) if c.verifier == "railway_autodeploy_on"]
    assert claims, "the standing autodeploy claim is missing from DOC_CLAIMS"
    behind = {
        "railway": {
            "deployments": [{"id": "x", "status": "SUCCESS", "commit_sha": "0" * 40}]
        },
        "repo": {"main_head": "f" * 40},
    }
    assert reconcile.check(claims, behind)[0].status == reconcile.UNVERIFIED
    current = {
        "railway": {
            "deployments": [{"id": "x", "status": "SUCCESS", "commit_sha": "f" * 40}]
        },
        "repo": {"main_head": "f" * 40},
    }
    assert reconcile.check(claims, current)[0].status == reconcile.OK
    failed_on_head = {
        "railway": {
            "deployments": [{"id": "x", "status": "FAILED", "commit_sha": "f" * 40}]
        },
        "repo": {"main_head": "f" * 40},
    }
    finding = reconcile.check(claims, failed_on_head)[0]
    assert finding.status == reconcile.UNVERIFIED
    assert "did not succeed" in finding.detail


def test_a_failed_push_build_still_contradicts_autodeploy_disabled():
    """For the disabled claim the trigger firing is the contradiction,
    whatever became of the build afterwards."""
    claims = reconcile.doc_claims({SPEC_DOC: "here autodeploy is disabled, still"})
    failed_on_head = {
        "railway": {
            "deployments": [{"id": "x", "status": "FAILED", "commit_sha": "f" * 40}]
        },
        "repo": {"main_head": "f" * 40},
    }
    finding = _finding(reconcile.check(claims, failed_on_head), "autodeploy is disabled")
    assert finding.status == reconcile.DRIFT


# ---------------------------------------------------------------------------
# The census claim
# ---------------------------------------------------------------------------


def test_a_changed_workflow_count_demands_a_doc_amendment():
    claims = [c for c in reconcile.doc_claims(reconcile._read_doc_texts()) if c.verifier == "n8n_total"]
    assert claims, "the census claim is missing from DOC_CLAIMS"
    fifty_seven = {str(i): {"name": str(i), "active": False} for i in range(57)}
    observations = _n8n_observation(workflows=fifty_seven, webhooks={})
    assert reconcile.check(claims, observations)[0].status == reconcile.DRIFT
    fifty_eight = {str(i): {"name": str(i), "active": False} for i in range(58)}
    observations = _n8n_observation(workflows=fifty_eight, webhooks={})
    assert reconcile.check(claims, observations)[0].status == reconcile.OK


# ---------------------------------------------------------------------------
# The fetch layer's pure edges
# ---------------------------------------------------------------------------


def test_disabled_webhook_nodes_are_skipped():
    """A disabled node on the claimed path must not shadow the enabled one."""
    detail = {
        "nodes": [
            {
                "type": "n8n-nodes-base.webhook",
                "disabled": True,
                "parameters": {"path": "devon-capture", "authentication": "none"},
            },
            {
                "type": "n8n-nodes-base.webhook",
                "parameters": {
                    "path": "devon-capture",
                    "authentication": "headerAuth",
                    "httpMethod": "POST",
                },
            },
            {"type": "n8n-nodes-base.set", "parameters": {}},
        ]
    }
    nodes = reconcile.webhook_nodes(detail)
    assert nodes == [{"path": "devon-capture", "auth": "headerAuth", "method": "POST"}]


def test_a_self_referential_host_read_is_unverified():
    """When the read defaulted to the vault's own host, agreement is an echo."""
    claims = reconcile.vault_claims(webhooks={}, workflows={})
    echo = {
        "n8n": {
            "host": "https://thequietoperator.app.n8n.cloud",
            "host_source": "vault_default",
            "workflows": {},
            "webhooks": {},
        }
    }
    finding = _finding(reconcile.check(claims, echo), "N8N_HOST")
    assert finding.status == reconcile.UNVERIFIED
    assert "falsifiable" in finding.detail

    independent = {
        "n8n": {
            "host": "https://thequietoperator.app.n8n.cloud",
            "host_source": "env",
            "workflows": {},
            "webhooks": {},
        }
    }
    assert _finding(reconcile.check(claims, independent), "N8N_HOST").status == reconcile.OK

    elsewhere = {
        "n8n": {
            "host": "https://n8n.editforge.online",
            "host_source": "env",
            "workflows": {},
            "webhooks": {},
        }
    }
    assert _finding(reconcile.check(claims, elsewhere), "N8N_HOST").status == reconcile.DRIFT


# ---------------------------------------------------------------------------
# Missing sources fail honest, not green
# ---------------------------------------------------------------------------


def test_a_missing_source_is_unverified_never_ok():
    claims = reconcile.vault_claims()
    findings = reconcile.check(claims, {"n8n": {"error": "N8N_SOURCE_KEY is not set"}})
    assert {finding.status for finding in findings} == {reconcile.UNVERIFIED}


def test_exit_codes_fail_on_drift_and_optionally_on_unverified():
    claim = reconcile.Claim("r", "s", "n8n_host", "https://x")
    drifted = [reconcile.Finding(claim, reconcile.DRIFT, "")]
    unverified = [reconcile.Finding(claim, reconcile.UNVERIFIED, "")]
    clean = [reconcile.Finding(claim, reconcile.OK, "")]
    assert reconcile.exit_code(drifted) == 1
    assert reconcile.exit_code(drifted, strict=True) == 1
    assert reconcile.exit_code(unverified) == 0
    assert reconcile.exit_code(unverified, strict=True) == 1
    assert reconcile.exit_code(clean, strict=True) == 0


# ---------------------------------------------------------------------------
# The prose ruling class, surfaced rather than trusted
# ---------------------------------------------------------------------------


def test_every_open_ruling_is_enumerated():
    rulings = dict(reconcile.open_rulings())
    assert "vault.WEBHOOKS['devon-capture']" in rulings
    assert "vault.WEBHOOKS['devon-approve-request']" in rulings


def test_the_report_carries_rulings_and_a_verdict():
    claim = reconcile.Claim("r", "s", "n8n_host", "https://x")
    findings = [reconcile.Finding(claim, reconcile.OK, "fine")]
    report = reconcile.render(findings, [("vault.WEBHOOKS['devon-capture']", "a ruling")])
    assert "cannot rot silently" in report
    assert "No drift" in report
    drifted = [reconcile.Finding(claim, reconcile.DRIFT, "wrong")]
    report = reconcile.render(drifted, [])
    assert "Correct the record or the estate" in report


# ---------------------------------------------------------------------------
# House law
# ---------------------------------------------------------------------------


def test_the_new_files_carry_no_banned_marks():
    """scripts/ and root tests sit outside test_devon_integrity's sweep, so
    the reconciler polices its own files by the same rule."""
    banned = (chr(0x2014), chr(0x2013))  # em dash, en dash, built not written
    for path in (ROOT / "scripts" / "estate_reconcile.py", pathlib.Path(__file__)):
        text = path.read_text(encoding="utf-8")
        offenders = [line for line in text.splitlines() if any(m in line for m in banned)]
        assert not offenders, f"banned dash in {path.name}: {offenders[:3]}"


# ---------------------------------------------------------------------------
# The records the DEVON and Hermes audit of 2026-09-02 (item 14) corrected
# ---------------------------------------------------------------------------

HERMES_DOC = "docs/devon/SYS_OPS_devon-hermes-stack-status_v2_2026-08-25.md"


def _repo_observations():
    return {
        "repo": {
            "alembic_head": reconcile._alembic_head(),
            "files": reconcile._pinned_files_present(),
            "image_files": reconcile._pinned_image_files(),
        }
    }


API_IMAGE = "infrastructure/docker/Dockerfile.api"
DEPLOYED = {"deployed_alembic_head": "015", "deployed_commit": "e69e412d23b6", "deployed_deployment": "2c4c5fb7"}


def test_a_resurrected_production_sha_is_caught():
    """FLAGSHIP, COMPLETION and GAUNTLET called d2aff6d production three
    merges after it moved. The corrected docs carry 57fdddb, dated, and the
    retired sentence is pinned so it cannot come back unnoticed."""
    claims = reconcile.doc_claims({"docs/GAUNTLET.md": "the live host is still d2aff6d, honest"})
    finding = _finding(reconcile.check(claims, {}), "docs/GAUNTLET.md ('still d2aff6d')")
    assert finding.status == reconcile.DRIFT
    assert "2026-09-02" in finding.detail
    assert "57fdddb" in finding.detail


def test_the_status_docs_no_longer_call_d2aff6d_production():
    for doc in ("FLAGSHIP.md", "COMPLETION.md", "docs/GAUNTLET.md"):
        text = (ROOT / doc).read_text(encoding="utf-8")
        assert "d2aff6d" not in text, doc
        assert "57fdddb" in text, doc


def test_a_resurrected_alembic_head_010_is_caught():
    claims = reconcile.doc_claims({HERMES_DOC: "deployed at Alembic head 010, one turn"})
    finding = _finding(reconcile.check(claims, {}), "Alembic head 010")
    assert finding.status == reconcile.DRIFT
    assert "2026-09-02" in finding.detail and "015" in finding.detail


def test_the_standing_alembic_head_is_judged_on_the_deployed_commit():
    """The doc describes the deployed database. The source tree is not
    evidence for that: only the newest successful Railway deployment's
    commit is, and without one the claim stays UNVERIFIED."""
    claims = [
        c for c in reconcile.doc_claims(reconcile._read_doc_texts()) if c.subject == "Alembic head 015"
    ]
    assert claims, "the standing Alembic head claim is missing from DOC_CLAIMS"
    ok = reconcile.check(claims, {"repo": {"alembic_head": "015", **DEPLOYED}})[0]
    assert ok.status == reconcile.OK
    assert "2c4c5fb7" in ok.detail and "e69e412d23b6" in ok.detail
    behind = reconcile.check(claims, {"repo": {"alembic_head": "016", **DEPLOYED}})[0]
    assert behind.status == reconcile.OK, "a migration in the tree but not deployed does not change what is deployed"
    moved = reconcile.check(claims, {"repo": {**DEPLOYED, "deployed_alembic_head": "016"}})[0]
    assert moved.status == reconcile.DRIFT
    source_only = reconcile.check(claims, {"repo": {"alembic_head": "015"}})[0]
    assert source_only.status == reconcile.UNVERIFIED
    assert "not what is deployed" in source_only.detail
    assert reconcile.check(claims, {})[0].status == reconcile.UNVERIFIED


def test_the_deployed_head_is_read_at_the_newest_successful_deployment():
    head_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    railway = {
        "deployments": [
            {"id": "failed-later", "status": "FAILED", "commit_sha": "0" * 40},
            {"id": "good", "status": "SUCCESS", "commit_sha": head_sha},
        ]
    }
    found = reconcile._deployed_alembic_head(railway)
    assert found["deployed_deployment"] == "good"
    assert found["deployed_commit"] == head_sha
    assert found["deployed_alembic_head"] == reconcile._alembic_head()
    unknown = reconcile._deployed_alembic_head(
        {"deployments": [{"id": "x", "status": "SUCCESS", "commit_sha": "f" * 40}]}
    )
    assert unknown["deployed_alembic_head"] is None
    assert "not in this clone" in unknown["deployed_reason"]
    assert reconcile._deployed_alembic_head({}) == {}
    assert reconcile._deployed_alembic_head({"error": "RAILWAY_API_TOKEN is not set"}) == {}


def test_the_doc_records_the_deployed_head_not_the_head_in_the_tree():
    """The tree runs ahead of production between a merge and its deploy.

    This test asserted the two were equal, which made every migration a red
    suite until someone edited the doc to claim a head that was not deployed
    yet. The doc describes the deployed database, so the standing claim is
    judged on the deployed commit (see the alembic_head verifier) and the
    tree only says what the next deploy will apply."""
    tree_head = reconcile._alembic_head()
    assert tree_head is not None and tree_head.isdigit()
    doc = (ROOT / HERMES_DOC).read_text(encoding="utf-8")
    standing = [
        c
        for c in reconcile.doc_claims(reconcile._read_doc_texts())
        if c.verifier == "alembic_head"
    ]
    assert len(standing) == 1, "exactly one standing head claim"
    assert standing[0].subject in doc, "the standing claim must quote the doc"
    assert standing[0].expected["head"] <= tree_head, (
        "the deployed head cannot be ahead of the migrations in the tree"
    )


def test_the_cron_entrypoint_ships_in_the_api_image():
    """Codex on the first cut: the checkout had dispatch.py, the image did
    not, so the documented cron line exited before dispatching."""
    shipped = reconcile._pinned_image_files()
    assert shipped[API_IMAGE]["dispatch.py"] is True
    assert "dispatch.py" in reconcile._image_copies()
    claims = [
        c for c in reconcile.doc_claims(reconcile._read_doc_texts()) if c.verifier == "image_file"
    ]
    assert len(claims) == 2
    for finding in reconcile.check(claims, {"repo": {"image_files": {API_IMAGE: {"dispatch.py": False}}}}):
        assert finding.status == reconcile.DRIFT
        assert "does not copy" in finding.detail
    for finding in reconcile.check(claims, {"repo": {"image_files": shipped}}):
        assert finding.status == reconcile.OK
    for finding in reconcile.check(claims, {}):
        assert finding.status == reconcile.UNVERIFIED


def test_a_cron_line_naming_a_missing_module_is_caught():
    texts = {
        "RUNBOOK.md": "cd /srv/app && python -m app.cli.dispatch >> log",
        "OPERATING.md": "cd /srv/app && python dispatch.py >> log",
    }
    files = {"app/cli/dispatch.py": False, "dispatch.py": True}
    findings = reconcile.check(reconcile.doc_claims(texts), {"repo": {"files": files}})
    stale = [f for f in findings if f.claim.record.startswith("RUNBOOK.md") and f.claim.subject == "python -m app.cli.dispatch"]
    assert stale[0].status == reconcile.DRIFT
    assert "does not exist" in stale[0].detail
    standing = [f for f in findings if f.claim.record.startswith("OPERATING.md") and f.claim.subject == "python dispatch.py"]
    assert standing[0].status == reconcile.OK


def test_the_standing_cron_line_names_a_file_that_exists():
    present = reconcile._pinned_files_present()
    assert present["dispatch.py"] is True
    assert present["app/cli/dispatch.py"] is False
    claims = [
        c for c in reconcile.doc_claims(reconcile._read_doc_texts())
        if c.subject == "python dispatch.py" and c.verifier == "repo_file"
    ]
    assert len(claims) == 2, "OPERATING.md and RUNBOOK.md each pin the cron line"
    for finding in reconcile.check(claims, {"repo": {"files": present}}):
        assert finding.status == reconcile.OK
    for finding in reconcile.check(claims, {}):
        assert finding.status == reconcile.UNVERIFIED


def test_the_retired_vercel_project_row_is_caught():
    claims = reconcile.doc_claims({"DEPLOY.md": "| meta-supreme-web | `apps/web` |"})
    finding = _finding(reconcile.check(claims, {}), "| meta-supreme-web |")
    assert finding.status == reconcile.DRIFT
    assert "meta-supreme-apex-genesis-web" in finding.detail


def test_every_audit_correction_holds_today():
    """The tripwires against the docs as committed and the repository as
    read: nothing retired came back, every standing sentence holds."""
    findings = reconcile.check(reconcile.doc_claims(reconcile._read_doc_texts()), _repo_observations())
    audited = [
        f for f in findings
        if f.claim.verifier in {"superseded", "alembic_head", "repo_file", "image_file", "quote_retired"}
    ]
    assert len(audited) >= 13
    for finding in audited:
        if finding.claim.verifier == "alembic_head":
            # Deployed evidence needs a Railway read; without one it is unverified, never OK.
            assert finding.status == reconcile.UNVERIFIED, finding
            continue
        assert finding.status in {reconcile.OK, reconcile.RETIRED}, finding

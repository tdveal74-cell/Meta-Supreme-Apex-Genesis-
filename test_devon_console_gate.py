"""Static contracts for the public DEVON gate and console chrome.

Cheap on purpose: no TestClient, no vendored import, no network.
Behavioural 404 probes live in deploy/soul/_selftest.py.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEPLOY = ROOT / "deploy" / "soul"
CONSOLE = (DEPLOY / "console.html").read_text()
MAIN = (DEPLOY / "main.py").read_text()
APP = (DEPLOY / "app.py").read_text()
WEBSITE = (ROOT / "website" / "index.html").read_text()
GAUNTLET = (ROOT / "docs" / "GAUNTLET.md").read_text()
FLAGSHIP = (ROOT / "FLAGSHIP.md").read_text()
COMPLETION = (ROOT / "COMPLETION.md").read_text()
HERMES_V2 = (
    ROOT / "docs" / "devon" / "SYS_OPS_devon-hermes-stack-status_v2_2026-08-25.md"
).read_text()


def _door_script() -> str:
    start = MAIN.index("document.getElementById('f').addEventListener('submit'")
    end = MAIN.index("</script>", start)
    return MAIN[start:end]


def _terminal_door() -> str:
    start = APP.index("TERMINAL_DOOR_HTML = ")
    end = APP.index("</script>", start) + len("</script>")
    return APP[start:end]


def test_gate_submit_does_not_put_the_token_in_the_url():
    script = _door_script()
    assert "location.href = '/console'" in script
    assert "?t=" not in script
    assert "encodeURIComponent(v)" in script  # cookie still encodes
    assert "sessionStorage.setItem('devon.soul.token'" in script
    assert "console.log" not in script


def test_console_strips_legacy_query_param_t_without_putting_it_back():
    assert "searchParams.get('t')" in CONSOLE
    assert "searchParams.delete('t')" in CONSOLE
    assert "history.replaceState" in CONSOLE
    assert "sessionStorage.setItem('devon.soul.token'" in CONSOLE
    assert re.search(r"location\.href\s*=\s*['\"][^'\"]*\?t=", CONSOLE) is None
    assert "/console?t=" not in CONSOLE
    adopt = CONSOLE[CONSOLE.index("adopt()") : CONSOLE.index("headers()")]
    assert "this.keep(handed)" not in adopt
    assert "searchParams.delete('t')" in adopt


def test_backend_does_not_accept_query_param_t_as_auth():
    presented = MAIN[MAIN.index("def _presented") : MAIN.index("def _require")]
    assert "if t and t.strip()" not in presented
    assert "never accepted" in presented.lower()
    assert "t: str | None = Query(default=None)" not in MAIN
    assert "t: str | None = Query(default=None)" not in APP
    assert "TOKEN_COOKIE" not in APP
    door = _terminal_door()
    assert "?t=" not in door
    assert "location.href = '/terminal'" in door


def test_flagship_tokens_are_navy_amber_surface_not_terracotta_primary():
    for blob in (CONSOLE, MAIN, _terminal_door()):
        assert "#0A1628" in blob
        assert "#D4A017" in blob
        assert "#F8F5F0" in blob
        root = blob[blob.index(":root") : blob.index(":root") + 600]
        assert "#C77B4A" not in root
        assert "--navy:#0A1628" in root.replace(" ", "")
        assert "--amber:#D4A017" in root.replace(" ", "")
    assert "#C77B4A" not in CONSOLE
    assert "#C77B4A" not in MAIN
    oxide = re.search(r"--oxide:([^;]+);", CONSOLE)
    assert oxide is not None
    assert "#C77B4A" not in oxide.group(1)


def test_console_html_has_no_backdrop_filter_blur():
    compact = re.sub(r"\s+", "", CONSOLE.lower())
    assert "backdrop-filter:blur" not in compact
    assert "backdrop-filter" not in CONSOLE.lower()


def test_website_has_no_backdrop_filter_blur():
    compact = re.sub(r"\s+", "", WEBSITE.lower())
    assert "backdrop-filter:blur" not in compact


def test_gate_is_top_aligned_with_full_width_44px_targets():
    assert "place-items:center" not in MAIN
    assert "align-items:flex-start" in MAIN
    assert "min-height:44px" in MAIN
    assert "OPEN THE CONSOLE" in MAIN
    assert "Soul recall is reads only." in MAIN
    assert "either soul index" in MAIN
    assert "/terminal is a separate Operator sandbox" in MAIN
    assert "no-referrer" in MAIN
    assert "referrer" in MAIN


def test_operator_terminal_door_matches_console_gate_chrome():
    door = _terminal_door()
    assert "place-items:center" not in door
    assert "align-items:flex-start" in door
    assert "min-height:44px" in door
    assert "sessionStorage.setItem('devon.soul.token'" in door
    assert "OPEN TERMINAL" in door
    assert "backdrop-filter" not in door.lower()
    assert "Live" not in door
    assert "LIVE" not in door


def test_gate_does_not_wear_a_live_badge():
    start = MAIN.index("DOOR_HTML")
    end = MAIN.index('"""', MAIN.index("</script>", start))
    door = MAIN[start:end]
    assert "Live" not in door
    assert "LIVE" not in door


def test_hermes_status_v2_is_ci_proven_not_operator_live():
    assert "CI-proven" in HERMES_V2
    assert "not operator-live" in HERMES_V2.lower()
    on_main = HERMES_V2[HERMES_V2.index("## On main") : HERMES_V2.index("## Governance")]
    assert "| Live" not in on_main
    assert "Live," not in on_main


def test_flagship_and_completion_refuse_closed_brain_and_live_inflation():
    for blob in (FLAGSHIP, COMPLETION):
        assert "not a closed 2nd-brain" in blob.lower()
        assert "2026-08-22 ID snapshot" in blob
        assert "executed: false" in blob
        assert "off by default" in blob.lower()
        assert "CI-proven" in blob
        assert "not operator-live" in blob.lower()


def test_gauntlet_ledger_floor_is_60_not_58_as_current_or_80():
    assert "| **Meta Supreme overall** | **60** |" in GAUNTLET
    assert "| 2nd-brain | 60 |" in GAUNTLET
    assert "Ledger floor" in GAUNTLET
    assert "~72" not in GAUNTLET
    assert "**~72**" not in GAUNTLET
    assert "**80**" not in GAUNTLET
    assert "**100**" not in GAUNTLET
    assert "CI-proven" in GAUNTLET
    assert "not operator-live" in GAUNTLET
    assert "executed: false" in GAUNTLET
    assert "2026-08-22 ID snapshot" in GAUNTLET
    assert "Flagship UI" in GAUNTLET and "38" in GAUNTLET
    assert "| Honesty | 72 |" in GAUNTLET
    assert "2nd-brain" in GAUNTLET
    assert "Human gates" in GAUNTLET and "86" in GAUNTLET
    assert "| DEVON |" in GAUNTLET
    assert "d2aff6d" in GAUNTLET
    assert "Not 80. Not 100." in GAUNTLET


def test_token_is_session_storage_and_a_short_cookie_not_a_year():
    for blob in (MAIN, APP, CONSOLE):
        assert "max-age=31536000" not in blob
        assert "max-age=43200" in blob
        assert "localStorage.setItem('devon.soul.token'" not in blob
        assert "sessionStorage.setItem('devon.soul.token'" in blob


def test_host_does_not_claim_writes_none_while_shipping_an_operator_terminal():
    assert '"writes": "none by design"' not in MAIN
    assert "soul_writes" in MAIN
    assert "separate Operator sandbox" in MAIN
    door = _terminal_door()
    assert "Operator terminal, not the soul console" in door
    term = (DEPLOY / "terminal.html").read_text()
    assert "Not the soul read lane" in term


def test_console_remember_uses_loop_when_platform_api_is_set():
    assert "Loop.configured" in CONSOLE
    assert "/api/v1/soul/propose" in CONSOLE
    assert "/api/v1/soul/approve" in CONSOLE
    assert "/api/v1/soul/commit" in CONSOLE
    assert "/api/v1/soul/find" in CONSOLE
    assert "rememberThroughLoop" in CONSOLE
    assert "Loop.propose" in CONSOLE
    assert "devon-soul.vercel.app" in CONSOLE
    assert "has no Postgres" in CONSOLE
    assert "LOOP CLOSED" in CONSOLE
    assert "localStorage is not memory" in CONSOLE
    assert "devon.soul.platform" in CONSOLE


def test_console_fail_closes_remember_when_platform_api_unset():
    assert "Loop.closedReason" in CONSOLE
    assert "refused rather than stored in localStorage" in CONSOLE
    assert "I cannot remember that" in CONSOLE
    # Area hints may still use devon.learning.v1; remember must not treat that as memory.
    start = CONSOLE.index('id="learnNote"')
    learn = " ".join(CONSOLE[start : start + 800].split())
    assert "not the remember path" in learn


def test_reconcile_does_not_rehydrate_localstorage_token():
    rec = CONSOLE[CONSOLE.index("reconcile()") : CONSOLE.index("keep(v)")]
    assert "this.get('token'" not in rec
    assert "localStorage.removeItem('devon.soul.token')" in rec
    assert "session || cookie" in rec or "session||cookie" in rec.replace(" ", "")


def test_console_does_not_claim_cookie_is_httponly():
    assert "; HttpOnly" not in CONSOLE
    assert "HttpOnly cookie" not in CONSOLE
    assert "httponly cookie" not in CONSOLE.lower()

def test_operator_console_splits_jwt_from_console_token():
    assert 'id="platTok"' in CONSOLE
    assert "Not CONSOLE_TOKEN" in CONSOLE
    assert "Not a platform JWT" in CONSOLE
    assert "devon.platform.jwt" in CONSOLE
    assert "CONSOLE_TOKEN for this soul host; platform JWT for app.main" not in CONSOLE


def test_pending_approvals_persist_in_session_storage_not_learning_v1():
    assert "devon.loop.pending" in CONSOLE
    assert "Loop.loadPending" in CONSOLE
    assert "Loop.setPending" in CONSOLE
    assert "Loop.dropPending" in CONSOLE
    refuse = CONSOLE[CONSOLE.index("async function ruleLoop") : CONSOLE.index("function rule(")]
    assert "Loop.dropPending" in refuse
    assert "Loop.approve" in refuse
    # REFUSE branch must not call approve/commit
    refuse_only = refuse[refuse.index("if(decision!=='approve')") : refuse.index("try {")]
    assert "Loop.approve" not in refuse_only
    assert "Loop.commit" not in refuse_only


def test_console_same_origin_default_and_vercel_fail_close():
    assert "same origin" in CONSOLE
    assert "onVercelSoulHost" in CONSOLE
    assert "operatorJwt" in CONSOLE
    assert "add_task" in CONSOLE and "KIND_FOR" in CONSOLE
    assert "whats_on_my_plate" in CONSOLE
    assert "findThroughLoop('*'" in CONSOLE or 'findThroughLoop("*"' in CONSOLE

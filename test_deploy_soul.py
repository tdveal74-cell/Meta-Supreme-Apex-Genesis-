"""Deployment integrity and behaviour tests for the DEVON Soul phone lane.

The phone lane stays read-only.  The hosted browser Operator is a separate
wrapper (`deploy/soul/app.py`) and must never weaken these tests.
"""

import json
import pathlib
import re
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent
DEPLOY = ROOT / "deploy" / "soul"

VENDORED = {
    "services/__init__.py": "services/__init__.py",
    "services/intelligence/soul.py": "services/intelligence/soul.py",
    "services/intelligence/providers/base.py": "services/intelligence/providers/base.py",
}
VENDORED.update(
    {
        f"services/devon/{p.name}": f"services/devon/{p.name}"
        for p in (ROOT / "services" / "devon").glob("*.py")
    }
)

SECRET_SHAPES = [
    ("a Pinecone key", r"pcsk_[A-Za-z0-9_-]{20,}"),
    ("a console token", r"dst_[0-9a-f]{32,}"),
    ("a capture token", r"dcp_[A-Za-z0-9_]{16,}"),
    ("an OpenAI key", r"\bsk-[A-Za-z0-9]{20,}"),
    ("an AWS access key id", r"\bAKIA[0-9A-Z]{16}\b"),
    ("a private key block", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    ("a Slack token", r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),
]

DELIBERATELY_DIFFERENT = {
    "main.py": "the read-only soul service itself",
    "app.py": (
        "the hosted Operator deployment wrapper; it imports the read-only soul "
        "app but executes commands only in Vercel Sandbox"
    ),
    "_selftest.py": "the behavioural probe below, run as a subprocess",
    "_conflict_selftest.py": (
        "the conflict-policy probe, run as a subprocess by "
        "test_deploy_soul_conflict_policy.py"
    ),
    "services/intelligence/__init__.py": (
        "trimmed: the platform version eagerly exposes the Council, which this lane does not ship"
    ),
    "services/intelligence/providers/__init__.py": (
        "trimmed: the platform version imports model providers this lane does not need"
    ),
}


def _shipped_modules():
    return sorted(
        str(p.relative_to(DEPLOY))
        for p in DEPLOY.rglob("*.py")
        if "__pycache__" not in p.parts
    )


@pytest.mark.parametrize("vendored,original", sorted(VENDORED.items()))
def test_vendored_module_matches_the_original(vendored, original):
    shipped = DEPLOY / vendored
    source = ROOT / original
    assert shipped.exists(), f"{vendored} is missing from deploy/soul"
    assert shipped.read_bytes() == source.read_bytes(), (
        f"{vendored} has drifted from {original}; the deployed soul service would answer from stale rules"
    )


def test_every_shipped_module_is_accounted_for():
    unaccounted = set(_shipped_modules()) - set(VENDORED) - set(DELIBERATELY_DIFFERENT)
    assert not unaccounted, f"shipped but unguarded: {sorted(unaccounted)}"


@pytest.mark.parametrize("name,reason", sorted(DELIBERATELY_DIFFERENT.items()))
def test_a_module_declared_different_really_is_shipped(name, reason):
    assert (DEPLOY / name).exists(), f"{name} is declared ({reason}) but not shipped"


def test_the_console_shipped_with_the_service_is_the_current_one():
    consoles = sorted(
        p
        for p in (ROOT / "docs" / "devon" / "assets").glob("SYS_OPS_devon-console_v*.html")
        if not p.name.startswith("SUPERSEDED_")
    )
    assert len(consoles) == 1, f"expected one current console, found {consoles}"
    assert (DEPLOY / "console.html").read_bytes() == consoles[0].read_bytes()


@pytest.mark.parametrize(
    "name",
    sorted(set(_shipped_modules()) | {"console.html", "terminal.html"}),
)
def test_no_shipped_file_hardcodes_a_secret(name):
    text = (DEPLOY / name).read_text(errors="ignore")
    for label, pattern in SECRET_SHAPES:
        hit = re.search(pattern, text)
        assert hit is None, (
            f"{name} contains something shaped like {label}: {hit.group(0)[:24]}..."
        )


@pytest.fixture(scope="module")
def probe():
    result = subprocess.run(
        [sys.executable, str(DEPLOY / "_selftest.py")],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, (
        f"the deployed service could not be exercised:\n{result.stderr[-3000:]}"
    )
    return json.loads(result.stdout.strip().splitlines()[-1])


# The one non-GET route the soul service may answer. Conflict-search is a
# recall query for the Build 12 learning gate: POST only because the claim
# rides in a body, auth-gated, and it writes nothing anywhere.
READ_ONLY_POST_ROUTES = [["POST", "/api/v1/soul/conflict-search"]]


def test_the_deployed_service_has_no_write_surface(probe):
    """The DEVON Soul app in main.py remains structurally read-only."""
    assert probe["effect_routes"] == READ_ONLY_POST_ROUTES, (
        f"the soul service answers {probe['effect_routes']}; Operator effects must stay outside main.py"
    )


def test_a_non_ascii_token_is_refused_not_a_crash(probe):
    assert probe["non_ascii_auth_status"] == 401
    assert probe["non_ascii_auth_recall"] == 401


def test_the_console_is_not_a_public_page(probe):
    assert probe["console_anonymous"] == 401
    assert probe["console_wrong_token"] == 401
    assert probe["anonymous_body_has_state"] is False
    assert probe["anonymous_body_has_airtable"] is False


def test_the_console_opens_for_a_token_in_a_header_or_on_the_url(probe):
    assert probe["console_query_token"] == 200
    assert probe["console_header_token"] == 200


def test_an_anonymous_caller_is_refused_before_anything_is_validated(probe):
    assert probe["recall_anonymous_no_q"] == 401
    assert probe["recall_anonymous_bad_q"] == 401
    assert probe["status_anonymous"] == 401
    assert probe["recall_authed_no_q"] == 422


def test_the_bare_hostname_is_a_door_for_a_person(probe):
    assert probe["root_browser_status"] == 200
    assert probe["root_browser_is_html"] is True
    assert probe["root_browser_has_paste_field"] is True
    assert probe["root_browser_leaks_state"] is False
    assert probe["root_json_still_json"].startswith("application/json")


@pytest.mark.parametrize(
    "key",
    [
        "cache_control_console_anon",
        "cache_control_console_authed",
        "cache_control_root",
        "cache_control_recall",
    ],
)
def test_nothing_this_service_returns_is_cacheable(probe, key):
    value = (probe[key] or "").lower()
    assert "no-store" in value, f"{key} is {probe[key]!r}"
    assert "public" not in value, f"{key} is {probe[key]!r}"


def test_the_root_fails_toward_the_door(probe):
    assert probe["root_no_accept_is_door"] is True
    assert probe["root_star_accept_is_door"] is True
    assert probe["root_safari_accept_is_door"] is True
    assert probe["root_chrome_accept_is_door"] is True


def test_a_closed_console_is_a_door_not_a_dead_end(probe):
    assert probe["console_closed_has_paste_field"] is True
    assert probe["no_token_console_has_paste_field"] is True


def test_the_door_names_which_wall_you_hit(probe):
    assert probe["console_no_token_says_so"] is True
    assert probe["console_bad_token_says_refused"] is True
    assert probe["console_bad_token_not_confused_with_no_token"] is True
    assert probe["no_token_console_names_the_host"] is True


def test_signing_in_once_means_once(probe):
    assert probe["console_cookie_opens_it"] == 200
    assert probe["console_cookie_serves_the_real_console"] is True
    assert probe["recall_cookie_opens_it"] == 200


def test_a_wrong_cookie_is_refused_like_anything_else(probe):
    assert probe["console_wrong_cookie_refused"] == 401


def test_a_header_beats_a_stale_cookie(probe):
    assert probe["header_beats_stale_cookie"] == 200


def test_health_is_the_one_open_route_and_says_only_what_is_set(probe):
    assert probe["health_anonymous"] == 200
    assert set(probe["health_body"]) == {"status", "console_token_set", "soul_key_set"}
    assert probe["no_token_health"] == 200


def test_an_unset_console_token_closes_the_service(probe):
    assert probe["no_token_status"] == 503
    assert probe["no_token_console"] == 503
    assert probe["no_token_console_body_has_state"] is False

def test_unknown_paths_are_branded_html_not_fastapi_json(probe):
    for key in ("health", "docs", "agents"):
        assert probe[f"unknown_{key}_status"] == 404
        assert "text/html" in (probe[f"unknown_{key}_content_type"] or "").lower()
        assert probe[f"unknown_{key}_is_fastapi_json"] is False
        body = probe[f"unknown_{key}_body"]
        assert "#0A1628" in body
        assert "#D4A017" in body
        assert "healthy" not in body.lower()
        assert "Return to the door" in body


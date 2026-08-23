"""
Deployment integrity for the soul service.

`deploy/soul/` vendors a copy of the modules it serves, because the host
builds only that directory and cannot reach up into the repository. A copy
is a drift risk: someone edits the real module, the deployed one quietly
keeps answering from last month's rules, and nothing says so.

These tests make that drift loud, and they check the service's behaviour
rather than its spelling. An earlier version of this file grepped main.py for
four decorator strings and called the result "structural". It was not: it
covered three of the shipped modules and none of the gate, and it passed
cleanly while /console was serving the whole estate map to anyone who asked.
"""

import json
import pathlib
import re
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent
DEPLOY = ROOT / "deploy" / "soul"

#: Shipped file -> the module it must match byte for byte.
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

#: Credential shapes, matched with enough trailing entropy to mean something.
#: A bare prefix is not a shape: "sk-" alone matched the `mask-image` in the
#: console's own stylesheet, and a guard that cries wolf gets deleted.
SECRET_SHAPES = [
    ("a Pinecone key", r"pcsk_[A-Za-z0-9_-]{20,}"),
    ("a console token", r"dst_[0-9a-f]{32,}"),
    ("a capture token", r"dcp_[A-Za-z0-9_]{16,}"),
    ("an OpenAI key", r"\bsk-[A-Za-z0-9]{20,}"),
    ("an AWS access key id", r"\bAKIA[0-9A-Z]{16}\b"),
    ("a private key block", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    ("a Slack token", r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),
]

#: Shipped files that are deliberately NOT copies, and why. Anything shipped
#: and absent from both maps fails `test_every_shipped_module_is_accounted_for`,
#: so a new vendored module cannot arrive unwatched.
DELIBERATELY_DIFFERENT = {
    "main.py": "the service itself, which exists only in the deployment",
    "_selftest.py": "the behavioural probe below, run as a subprocess",
    "services/intelligence/__init__.py": (
        "trimmed: the platform's version eagerly exposes the Council, which "
        "this lane does not ship and does not need"
    ),
    "services/intelligence/providers/__init__.py": (
        "trimmed: the platform's version imports every model provider; the "
        "soul layer raises the error types and calls no model"
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
    """A deployed module that has drifted from the real one is a lie."""
    shipped = DEPLOY / vendored
    source = ROOT / original
    assert shipped.exists(), (
        f"{vendored} is missing from deploy/soul. Re-vendor it, or the "
        f"deployed service imports something that is no longer there."
    )
    assert shipped.read_bytes() == source.read_bytes(), (
        f"{vendored} has drifted from {original}. The deployed soul service "
        f"would answer from stale rules. Copy the original over it."
    )


def test_every_shipped_module_is_accounted_for():
    """
    No module rides along unwatched.

    The previous guard listed three paths and globbed a fourth directory, so
    two shipped packages sat outside it entirely. Silence about a file is
    indistinguishable from a file that matches, which is the failure this
    closes: every .py under deploy/soul is either held identical or named
    here with the reason it differs.
    """
    unaccounted = set(_shipped_modules()) - set(VENDORED) - set(DELIBERATELY_DIFFERENT)
    assert not unaccounted, (
        f"shipped but unguarded: {sorted(unaccounted)}. Add each to VENDORED "
        f"if it is a copy, or to DELIBERATELY_DIFFERENT with the reason it "
        f"is not."
    )


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
    assert (DEPLOY / "console.html").read_bytes() == consoles[0].read_bytes(), (
        "deploy/soul/console.html is not the current console. Re-copy it."
    )


@pytest.mark.parametrize("name", sorted(set(_shipped_modules()) | {"console.html"}))
def test_no_shipped_file_hardcodes_a_secret(name):
    """
    Every shipped file, not just main.py.

    The old check read one file and looked for two literal prefixes, so a key
    pasted into the console or into a vendored module would have shipped
    without a word.
    """
    text = (DEPLOY / name).read_text(errors="ignore")
    for label, pattern in SECRET_SHAPES:
        hit = re.search(pattern, text)
        assert hit is None, (
            f"{name} contains something shaped like {label}: {hit.group(0)[:24]}... "
            f"Secrets come from the host environment and nowhere else, and "
            f"never from a file in the repository."
        )


# --------------------------------------------------------------------------
# Behaviour. Run in a subprocess: importing the service puts the vendored
# `services` tree first on sys.path, and two of those packages are trimmed,
# so an in-process import would hand the rest of the suite the wrong modules.
# --------------------------------------------------------------------------


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


def test_the_deployed_service_has_no_write_surface(probe):
    """
    Reads flow; this lane performs no effects, and that is now structural.

    Asserted against the router the app actually built, not against the
    presence of four decorator strings in one file. An effect reached through
    a GET, or through a router included from elsewhere, is caught here and
    was not caught before.
    """
    assert probe["effect_methods"] == [], (
        f"the soul service answers {probe['effect_methods']}. The phone lane "
        f"is reads only: a devon-soul write is an effect and belongs behind "
        f"the approval queue, not behind a shared token."
    )


def test_a_non_ascii_token_is_refused_not_a_crash(probe):
    """
    hmac.compare_digest raises TypeError on a str holding any byte above 127,
    and header values arrive latin-1 decoded, so one high byte in an
    Authorization header turned the gate into an uncaught 500. An anonymous
    caller could make the gate crash instead of refuse.
    """
    assert probe["non_ascii_auth_status"] == 401, probe["non_ascii_auth_status"]
    assert probe["non_ascii_auth_recall"] == 401, probe["non_ascii_auth_recall"]


def test_the_console_is_not_a_public_page(probe):
    """
    /console was open, on the reasoning that it "holds nothing until you sign
    in". It holds a baked-in STATE blob: every Drive folder id, every doctrine
    file id, the live Airtable base, every n8n workflow id, and every webhook
    path with its auth posture.
    """
    assert probe["console_anonymous"] == 401
    assert probe["console_wrong_token"] == 401
    assert probe["anonymous_body_has_state"] is False, (
        "the anonymous console response still carries the STATE blob"
    )
    assert probe["anonymous_body_has_airtable"] is False, (
        "the anonymous console response still names a live Airtable base"
    )


def test_the_console_opens_for_a_token_in_a_header_or_on_the_url(probe):
    """A browser cannot set a header, so the first load may carry ?t=."""
    assert probe["console_query_token"] == 200
    assert probe["console_header_token"] == 200


def test_an_anonymous_caller_is_refused_before_anything_is_validated(probe):
    """
    Declared-strict query parameters are validated before the handler body,
    so a caller holding no token got a 422 describing the endpoint's
    parameters. Nothing answers an anonymous caller except the refusal.
    """
    assert probe["recall_anonymous_no_q"] == 401
    assert probe["recall_anonymous_bad_q"] == 401
    assert probe["status_anonymous"] == 401
    # Validation still happens, once the caller has proved who they are.
    assert probe["recall_authed_no_q"] == 422


def test_health_is_the_one_open_route_and_says_only_what_is_set(probe):
    """
    Deliberate: the operator has to be able to see the service is up and what
    it is still missing without holding a credential. It reports two booleans
    and nothing else.
    """
    assert probe["health_anonymous"] == 200
    assert set(probe["health_body"]) == {"status", "console_token_set", "soul_key_set"}
    assert probe["no_token_health"] == 200


def test_an_unset_console_token_closes_the_service(probe):
    """Misconfiguration must close the door, never leave it standing open."""
    assert probe["no_token_status"] == 503
    assert probe["no_token_console"] == 503
    assert probe["no_token_console_body_has_state"] is False

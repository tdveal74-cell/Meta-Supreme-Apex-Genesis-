"""The platform console can sign in, and the password goes nowhere but the login.

Ruled by Tee 2026-10-16 on a card, after recall was switched on for Railway
api and could not be proven: the console's recall needs a CurrentUser JWT, the
console had no way to get one except pasting it, and the phone Tee runs it on
cannot copy a token out of another page. So the Soul Layer panel gained an
email and password form that posts to POST /api/v1/auth/login and keeps the
returned JWT in the same sessionStorage slot a pasted one uses.

These are static contracts on the served HTML, both copies. They prove the
shape of the code, not that a browser runs it; the executed proof is recorded
in the pull request that added this file.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONSOLES = {
    "deploy/soul/console.html": ROOT / "deploy" / "soul" / "console.html",
    "docs/devon/assets/SYS_OPS_devon-console_v10_2026-09-01.html": (
        ROOT / "docs" / "devon" / "assets" / "SYS_OPS_devon-console_v10_2026-09-01.html"
    ),
}


def _read(name: str) -> str:
    return CONSOLES[name].read_text()


def _function(src: str, name: str) -> str:
    """The text of a top level `function name(` or `async function name(`."""
    match = re.search(r"(?:async\s+)?function\s+" + re.escape(name) + r"\s*\(", src)
    assert match, f"function {name} is missing"
    start = match.start()
    nxt = re.search(r"\n(?:async\s+)?function\s+\w+\s*\(|\nconst\s+\w+\s*=", src[match.end():])
    end = match.end() + nxt.start() if nxt else len(src)
    return src[start:end]


def _submit_handler(src: str) -> str:
    start = src.index("signForm.onsubmit")
    end = src.index("$('soulTest').onclick", start)
    return src[start:end]


def test_both_consoles_carry_the_form():
    for name in CONSOLES:
        src = _read(name)
        assert '<form id="signForm"' in src, name
        # If the script never runs, the browser must submit nothing, and a
        # forced submit must not put the password in a URL that a proxy logs.
        form_tag = re.search(r'<form id="signForm"[^>]*>', src).group(0)
        assert 'method="post"' in form_tag, name
        assert 'onsubmit="return false"' in form_tag, name
        assert "action=" not in form_tag, name
        assert re.search(r'<input id="signEmail"[^>]*type="email"', src), name
        assert re.search(r'<input id="signEmail"[^>]*autocomplete="username"', src), name
        assert re.search(r'<input id="signPass"[^>]*type="password"', src), name
        assert re.search(r'<input id="signPass"[^>]*autocomplete="current-password"', src), name
        assert '<button class="tgl" id="signGo" type="submit">SIGN IN</button>' in src, name


def test_the_password_goes_to_the_login_route_and_nowhere_else():
    for name in CONSOLES:
        src = _read(name)
        body = _function(src, "signIn")
        assert "Loop.getBase() + '/api/v1/auth/login'" in body, name
        assert "method: 'POST'" in body, name
        assert "JSON.stringify({ email: email, password: password })" in body, name
        # One fetch, to one place.
        assert body.count("fetch(") == 1, name
        # The console never creates an account: registration stays behind the
        # invite key on the Command Center.
        assert "/auth/register" not in src, name
        assert "registration_key" not in src, name


def test_the_password_is_never_stored_or_logged():
    for name in CONSOLES:
        src = _read(name)
        for line in src.splitlines():
            if "setItem(" in line:
                assert not re.search(r"pass", line, re.IGNORECASE), f"{name}: {line.strip()}"
        handler = _submit_handler(src)
        assert "console.log" not in handler, name
        assert "console.log" not in _function(src, "signIn"), name
        # The field is cleared whatever the login returned.
        opener = "} finally {"
        finally_block = handler[handler.index(opener) + len(opener) :]
        finally_block = finally_block[: finally_block.index("}")]
        assert "passEl.value = ''" in finally_block, name


def test_only_the_token_is_kept_and_only_in_session_storage():
    for name in CONSOLES:
        src = _read(name)
        handler = _submit_handler(src)
        assert "keepOperatorJwt(token)" in handler, name
        assert "localStorage" not in handler, name
        assert "localStorage" not in _function(src, "signIn"), name
        keep = _function(src, "keepOperatorJwt")
        assert "sessionStorage.setItem('devon.platform.jwt', handed)" in keep, name
        assert "localStorage.setItem('devon.platform.jwt'" not in src, name


def test_a_refused_sign_in_keeps_nothing():
    for name in CONSOLES:
        handler = _submit_handler(_read(name))
        # The token is only kept after the try has produced one; a refusal
        # returns before keepOperatorJwt is reached.
        assert handler.index("if (!token) {") < handler.index("keepOperatorJwt(token)"), name
        refusal = handler[handler.index("if (!token) {") :]
        refusal = refusal[: refusal.index("}")]
        assert "return;" in refusal, name


def test_the_form_exists_only_on_the_platform_console():
    for name in CONSOLES:
        src = _read(name)
        assert "if (signForm) signForm.style.display = soulHost ? 'none' : '';" in src, name
        assert "if (signForm && !soulHost) {" in src, name


def test_every_failure_says_what_happened_and_that_nothing_was_kept():
    for name in CONSOLES:
        says = _function(_read(name), "signInSays")
        for reason in ("refused", "disabled", "shape", "notoken"):
            assert f"m === '{reason}'" in says, f"{name}: {reason}"
        returns = [line.strip() for line in says.splitlines() if "return " in line]
        assert len(returns) == 6, f"{name}: {returns}"
        for line in returns:
            assert re.search(r"[Nn]othing was kept\.';$", line), f"{name}: {line}"


def test_a_soul_search_that_did_not_finish_never_reads_as_empty():
    """The platform asks "what did we decide about" through /soul/find.

    That answer carries soul_recall_enabled and soul_errors beside the hits.
    The console drew only the hits until 2026-10-16, so a Pinecone search that
    failed looked exactly like a soul with nothing in it, which is the one
    reading the recall proof has to tell apart.
    """
    for name in CONSOLES:
        src = _read(name)
        start = src.index("async function findThroughLoop(")
        body = src[start : src.index("function handle(", start)]
        assert "body.soul_errors || []" in body, name
        assert "body.soul_recall_enabled !== true" in body, name
        assert "SOUL PARTIAL" in body and "SOUL OFF" in body and "SOUL SEARCHED" in body, name
        # Off is checked first, then a failure, and only then an empty soul.
        assert body.index("SOUL OFF") < body.index("SOUL PARTIAL") < body.index("SOUL SEARCHED"), name
        assert "esc(soulErrors.join('; '))" in body, name


def test_an_unsigned_console_says_so_rather_than_jwt_refused():
    for name in CONSOLES:
        src = _read(name)
        assert "return operatorJwt() ? 'SIGN IN AGAIN' : 'NOT SIGNED IN';" in src, name
        assert "'JWT REFUSED'" not in src, name

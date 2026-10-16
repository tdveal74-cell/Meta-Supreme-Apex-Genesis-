"""The platform console can sign in, and the password goes nowhere but the login.

Ruled by Tee 2026-10-16 on a card. He set SOUL_RECALL_ENABLED and the
Pinecone key on Railway api on 2026-10-15 (deployment 84a15677), and recall
still could not be proven: the console's recall needs a CurrentUser JWT, the
console had no way to get one except pasting it, and the phone Tee runs it on
cannot copy a token out of another page. So the Soul Layer panel gained an
email and password form that posts to POST /api/v1/auth/login on the page's
own origin and keeps the returned JWT in the sessionStorage slot a pasted one
uses.

These are static contracts on the served HTML, both copies. They pin the
shape of the code, and a critic proved on the first version that a determined
edit can keep every pinned string while breaking the behaviour, so they are
the cheap guard and not the proof. The proof is executed:
apps/web/scripts/console-smoke.mjs drives the console in Chromium in
panel-smoke-ci.yml, signs in wrong and right, asks a recall, and fails if the
password reaches storage, a cookie, the console, the page, a URL or any
request but the login.
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

# Every line of the console that names the password, the password field or
# the variable holding it, exactly. A new line that touches the password, an
# alias, a second destination or a log, has to be added here on purpose, in
# a diff a reviewer reads.
PASSWORD_LINES = {
    ".keyrow select,.keyrow input[type=text],.keyrow input[type=password],.keyrow input[type=email]{",
    "your DEVON email and password, or paste one. PLATFORM is not",
    '<input id="soulTok" type="password" placeholder="CONSOLE_TOKEN for this soul host only. Not a platform JWT.">',
    "submitted natively, no password could reach a URL or a body. -->",
    '<label for="signPass">PASSWORD</label>',
    '<input id="signPass" type="password" autocomplete="current-password"',
    '<input id="platTok" type="password" placeholder="platform CurrentUser JWT. Not CONSOLE_TOKEN.">',
    '<input id="ruleKey" type="password" placeholder="DEVON_RULING_KEY. Approves; the JWT alone never does.">',
    "another page can still reach recall. The password goes to POST",
    "later password to whatever origin it names. A redirect is refused rather",
    "async function signIn(email, password) {",
    "body: JSON.stringify({ email: email, password: password })",
    "if (m === 'refused') return 'Wrong email or password. Nothing was kept.';",
    "const emailEl = $('signEmail'), passEl = $('signPass');",
    "const password = passEl.value || '';",
    "if (!email || !password) {",
    "note.textContent = 'Email and password, both.';",
    "token = await signIn(email, password);",
    "passEl.value = '';",
    ": 'Not signed in. Sign in with your email and password in the Soul Layer panel, then ask again.')",
}

# Ways a value leaves the page or lands at rest, other than the one login fetch.
EXITS = (
    "console.",
    "sendBeacon",
    "XMLHttpRequest",
    "WebSocket",
    "EventSource",
    "document.cookie",
    "localStorage",
    "sessionStorage[",
    "window.open",
    "location.",
    "history.",
    "postMessage",
    "innerHTML",
)


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


def test_both_consoles_carry_the_form_and_ship_it_hidden():
    for name in CONSOLES:
        src = _read(name)
        form_tag = re.search(r'<form id="signForm"[^>]*>', src).group(0)
        # Shown only by wireSoul on the platform host, so a browser that never
        # ran the script never offers it.
        assert re.search(r"\shidden(?=[\s>])", form_tag), f"{name}: {form_tag}"
        # The second layer: a native submit would be a POST to this page,
        # never a GET, and the inline handler cancels it outright.
        assert 'method="post"' in form_tag, name
        assert 'onsubmit="return false"' in form_tag, name
        assert "action=" not in form_tag, name
        email = re.search(r'<input id="signEmail"[^>]*>', src, re.S).group(0)
        password = re.search(r'<input id="signPass"[^>]*>', src, re.S).group(0)
        assert 'type="email"' in email and 'autocomplete="username"' in email, name
        assert 'type="password"' in password, name
        assert 'autocomplete="current-password"' in password, name
        # No name, so a native submission carries neither field in its body.
        assert "name=" not in email and "name=" not in password, name
        assert '<button class="tgl" id="signGo" type="submit">SIGN IN</button>' in src, name


def test_the_password_goes_to_this_origins_login_and_nowhere_else():
    for name in CONSOLES:
        src = _read(name)
        body = _function(src, "signIn")
        # Exactly this origin. Loop.getBase() follows the PLATFORM field, and
        # a base saved there would carry every later password away with it.
        assert "fetch('/api/v1/auth/login', {" in body, name
        assert "Loop.getBase()" not in body and "Soul.base()" not in body, name
        assert "credentials: 'same-origin'" in body, name
        assert "redirect: 'error'" in body, name
        assert "method: 'POST'" in body, name
        assert body.count("fetch(") == 1, name
        handler = _submit_handler(src)
        assert "fetch(" not in handler, name
        for exit_ in EXITS:
            assert exit_ not in body, f"{name}: signIn uses {exit_}"
            assert exit_ not in handler, f"{name}: the submit handler uses {exit_}"
        # The console never creates an account: registration stays behind the
        # invite key on the Command Center.
        assert "/auth/register" not in src, name
        assert "registration_key" not in src, name


def test_only_known_lines_touch_the_password():
    for name in CONSOLES:
        src = _read(name)
        found = {
            line.strip()
            for line in src.splitlines()
            if re.search(r"\bpassword\b|passEl|signPass", line)
        }
        assert found == PASSWORD_LINES, (
            f"{name}: lines touching the password changed.\n"
            f"new: {sorted(found - PASSWORD_LINES)}\nmissing: {sorted(PASSWORD_LINES - found)}"
        )


def test_the_password_field_is_cleared_whatever_comes_back():
    for name in CONSOLES:
        handler = _submit_handler(_read(name))
        opener = "} finally {"
        finally_block = handler[handler.index(opener) + len(opener) :]
        finally_block = finally_block[: finally_block.index("}")]
        assert "passEl.value = ''" in finally_block, name
        assert handler.count("passEl.value = ''") == 1, name


def test_only_the_token_is_kept_and_only_in_session_storage():
    for name in CONSOLES:
        src = _read(name)
        handler = _submit_handler(src)
        assert handler.count("keepOperatorJwt(token)") == 1, name
        keep = _function(src, "keepOperatorJwt")
        assert "sessionStorage.setItem('devon.platform.jwt', handed)" in keep, name
        assert "localStorage" not in keep, name
        assert keep.count("setItem(") == 1, name
        assert "localStorage.setItem('devon.platform.jwt'" not in src, name


def test_a_refused_sign_in_keeps_nothing_and_does_not_call_a_kept_one_dead():
    for name in CONSOLES:
        handler = _submit_handler(_read(name))
        assert handler.index("if (!token) {") < handler.index("keepOperatorJwt(token)"), name
        refusal = handler[handler.index("if (!token) {") : handler.index("keepOperatorJwt(token)")]
        # Both refusal paths, signed out and still signed in, return before
        # the keep.
        assert refusal.count("return;") == 2, name
        # With an earlier sign-in still kept, the API is asked rather than the
        # badge being flipped to SIGN IN AGAIN over a live token.
        assert "Your earlier sign-in is still kept for this tab." in refusal, name
        assert "Soul.status()" in refusal, name
        assert "SIGN IN AGAIN" not in refusal, name


def test_the_form_is_revealed_in_one_place_and_only_on_the_platform():
    for name in CONSOLES:
        src = _read(name)
        assert "if (signForm) signForm.hidden = soulHost;" in src, name
        assert src.count("signForm.hidden") == 1, name
        assert "signForm.style" not in src, name
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

    That answer carries soul_recall_enabled, soul_errors and soul_withheld
    beside the hits. The console drew only the hits until 2026-10-16, so a
    Pinecone search that failed looked exactly like a soul with nothing in it,
    which is the one reading the recall proof has to tell apart. A recall that
    withheld records is not a measured empty either: each withheld record used
    a slot in the search window.
    """
    for name in CONSOLES:
        src = _read(name)
        start = src.index("async function findThroughLoop(")
        body = src[start : src.index("function handle(", start)]
        assert "body.soul_errors || []" in body, name
        assert "body.soul_recall_enabled !== true" in body, name
        assert body.index("SOUL OFF") < body.index("SOUL PARTIAL") < body.index("SOUL SEARCHED"), name
        assert "esc(soulErrors.join('; '))" in body, name
        assert "} else if (!soulHits.length && !withheld) {" in body, name
        assert "SOUL WINDOW" in body and "esc(String(withheld))" in body, name


def test_an_unsigned_recall_points_at_the_sign_in():
    for name in CONSOLES:
        src = _read(name)
        start = src.index("async function findThroughLoop(")
        body = src[start : src.index("function handle(", start)]
        assert "e.status === 401" in body, name
        assert "Not signed in. Sign in with your email and password in the Soul Layer panel" in body, name
        # Loop.find hands the status up, or the branch above can never fire.
        find = src[src.index("async find(q, kind) {") :]
        find = find[: find.index("return res.json();")]
        assert "failure.status = res.status;" in find, name


def test_an_unsigned_console_says_so_rather_than_jwt_refused():
    for name in CONSOLES:
        src = _read(name)
        assert "return operatorJwt() ? 'SIGN IN AGAIN' : 'NOT SIGNED IN';" in src, name
        assert "'JWT REFUSED'" not in src, name


def test_a_chip_fills_the_command_line_and_never_sends_it():
    """Three example chips are remembers; one tap used to write a proposal."""
    for name in CONSOLES:
        src = _read(name)
        block = src[src.index("EXAMPLES.forEach(") :]
        block = block[: block.index("});") + 3]
        assert "handle(" not in block, name
        assert "cmd.value=x;" in block, name


def test_the_gate_countdown_leaves_cards_without_a_deadline_alone():
    for name in CONSOLES:
        src = _read(name)
        loop = src[src.index("document.querySelectorAll('.cd').forEach(") :]
        loop = loop[: loop.index("});")]
        assert "if(!n.dataset.exp) return;" in loop, name
        assert loop.index("if(!n.dataset.exp) return;") < loop.index("fmtLeft("), name

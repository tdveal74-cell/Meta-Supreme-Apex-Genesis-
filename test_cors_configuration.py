"""The CORS allowlist should say what it will accept before it refuses anyone.

Written on 2026-08-27, the day a production outage came down to this and took
Railway HTTP log forensics to find. Every browser call from the Command Center
failed. The API logged 200 for the reads and 400 for the preflights, both of
which are what a healthy service looks like from the server side, and nothing in
any log named the origins the process would accept.

The tests below are mostly about the two allowlist states that look fine and are
not: an entry no browser Origin header can ever equal, and a deployed API whose
every entry points at localhost.
"""

from __future__ import annotations

import logging

from app.core.cors import (
    cors_startup_report,
    is_localhost_only,
    is_malformed,
    log_cors_configuration,
    malformed_origins,
)

GOOD = "https://meta-supreme-apex-genesis-web.vercel.app"


def levels(origins, environment) -> list[str]:
    return [level for level, _ in cors_startup_report(origins, environment)]


def text(origins, environment) -> str:
    return " | ".join(message for _, message in cors_startup_report(origins, environment))


# ---------------------------------------------------------------------------
# Entries that are present, plausible and dead
# ---------------------------------------------------------------------------


def test_a_trailing_slash_can_never_match_an_origin_header() -> None:
    """The exact shape that is easiest to type and impossible to notice.

    A browser sends `https://host` with no trailing slash, and Starlette compares
    by string equality, so there is no near miss to fall back on.
    """
    assert is_malformed(f"{GOOD}/")
    assert not is_malformed(GOOD)


def test_stray_whitespace_is_caught_like_the_trailing_space_that_bit_us_before() -> None:
    """Same family as the Railway variable named with a trailing space."""
    assert is_malformed(f" {GOOD}")
    assert is_malformed(f"{GOOD} ")


def test_a_path_or_query_or_fragment_is_not_an_origin() -> None:
    assert is_malformed(f"{GOOD}/command-center")
    assert is_malformed(f"{GOOD}?x=1")
    assert is_malformed(f"{GOOD}#top")


def test_a_missing_or_wrong_scheme_is_refused() -> None:
    assert is_malformed("meta-supreme-apex-genesis-web.vercel.app")
    assert is_malformed("ftp://example.com")
    assert not is_malformed("http://localhost:3000")


def test_the_wildcard_is_a_policy_choice_not_a_typo() -> None:
    """Starlette reads `*` as allow-all, so flagging it as malformed would lie."""
    assert not is_malformed("*")
    assert malformed_origins(["*", GOOD]) == ()


def test_malformed_entries_are_reported_by_value() -> None:
    broken = malformed_origins([GOOD, f"{GOOD}/", "nope.example.com"])
    assert broken == (f"{GOOD}/", "nope.example.com")


# ---------------------------------------------------------------------------
# A deployed API that only its own machine can call
# ---------------------------------------------------------------------------


def test_the_shipped_default_is_loopback_only() -> None:
    """Documents why the warning exists: the default is correct locally and
    catastrophic once deployed, and nothing about it changes on the way."""
    from app.core.config import Settings

    assert is_localhost_only(Settings().CORS_ORIGINS)


def test_one_real_origin_is_enough_to_stop_being_loopback_only() -> None:
    assert not is_localhost_only(["http://localhost:3000", GOOD])


def test_loopback_hosts_are_recognised_with_and_without_ports() -> None:
    assert is_localhost_only(["http://localhost:3000", "http://127.0.0.1", "http://[::1]:8080"])


def test_a_broken_remote_entry_does_not_count_as_reach() -> None:
    """The subtle case, and the one that would waste an afternoon.

    An allowlist holding localhost plus a remote entry with a trailing slash
    looks like it serves a front end. It does not: the broken entry matches
    nothing, so the deployment is still loopback only and must still warn.
    """
    assert is_localhost_only(["http://localhost:3000", f"{GOOD}/"])


def test_an_empty_allowlist_is_loopback_only_because_it_reaches_nobody() -> None:
    assert is_localhost_only([])


def test_the_wildcard_is_not_loopback_only() -> None:
    assert not is_localhost_only(["*"])


# ---------------------------------------------------------------------------
# What gets said at startup
# ---------------------------------------------------------------------------


def test_the_origins_are_always_stated_even_when_healthy() -> None:
    """The point is the receipt, not the alarm. A correct allowlist still prints."""
    report = cors_startup_report([GOOD], "production")
    assert levels([GOOD], "production") == ["info"]
    assert GOOD in report[0][1]
    assert "1 origin(s)" in report[0][1]


def test_a_deployed_localhost_only_allowlist_warns() -> None:
    body = text(["http://localhost:3000"], "production")
    assert "warning" in levels(["http://localhost:3000"], "production")
    assert "no deployed front end can call this API" in body
    assert "400" in body


def test_the_same_allowlist_is_silent_in_development() -> None:
    """Loopback only is the right answer locally, so warning there trains people
    to ignore the warning that matters."""
    assert levels(["http://localhost:3000"], "development") == ["info"]
    assert levels(["http://localhost:3000"], "test") == ["info"]


def test_malformed_entries_warn_and_name_themselves() -> None:
    body = text([GOOD, f"{GOOD}/"], "production")
    assert "warning" in levels([GOOD, f"{GOOD}/"], "production")
    assert f"{GOOD}/" in body
    assert "trailing slash" in body


def test_both_problems_can_be_reported_at_once() -> None:
    report = cors_startup_report([f"{GOOD}/"], "production")
    assert [level for level, _ in report] == ["info", "warning", "warning"]


# ---------------------------------------------------------------------------
# The wiring, because a report nobody logs is the silence this ends
# ---------------------------------------------------------------------------


def test_the_report_actually_reaches_the_log_at_the_right_levels(caplog) -> None:
    log = logging.getLogger("cors-test")
    with caplog.at_level(logging.INFO, logger="cors-test"):
        log_cors_configuration(log, ["http://localhost:3000"], "production")

    emitted = [(record.levelno, record.getMessage()) for record in caplog.records]
    assert [level for level, _ in emitted] == [logging.INFO, logging.WARNING]
    assert "loopback" in emitted[1][1]


def test_a_healthy_configuration_logs_without_warning(caplog) -> None:
    log = logging.getLogger("cors-test-healthy")
    with caplog.at_level(logging.INFO, logger="cors-test-healthy"):
        log_cors_configuration(log, [GOOD], "production")

    assert [record.levelno for record in caplog.records] == [logging.INFO]


def test_default_cors_does_not_allow_the_vercel_soul_host() -> None:
    from app.core.config import Settings
    origins = Settings().CORS_ORIGINS
    assert "https://devon-soul.vercel.app" not in origins
    assert is_localhost_only(origins)


# ---------------------------------------------------------------------------
# Why loopback origins are tolerable in the production allowlist, guarded
# ---------------------------------------------------------------------------
#
# Added 2026-09-04, after the three retired `meta-supreme-web` hosts were
# removed from the production CORS_ORIGINS and the question "should the two
# loopback entries go too" was actually investigated rather than answered from
# the generic rule.
#
# The answer was no, and it rests on ONE property of this app: authentication
# is a bearer token in the Authorization header, which a browser never attaches
# automatically to a cross-origin request, and which a page at one origin
# cannot read out of another origin's storage. There is no auth cookie. So an
# origin on the allowlist gains no ambient authority, and `allow_credentials`
# grants a hostile local page nothing it did not already have.
#
# That reasoning collapses the moment auth moves to a cookie. Then
# `http://localhost:3000` in a deployed allowlist is a live CSRF path, and
# nothing about the allowlist itself would look any different. These two tests
# are the tripwire for exactly that refactor: they fail on the day it lands,
# in the job that already runs test_security.py, and the failure says what to
# do about the allowlist.


def test_auth_is_a_bearer_header_so_allowlisted_origins_gain_no_ambient_authority() -> None:
    from fastapi.security import HTTPBearer

    from app.security import deps

    assert isinstance(deps.security_scheme, HTTPBearer), (
        "Authentication is no longer an Authorization header. A bearer token is "
        "what makes the loopback entries in the production CORS allowlist safe: "
        "a browser does not attach it cross-origin and a hostile page cannot "
        "read it from another origin's storage. If auth now travels by cookie, "
        "remove http://localhost:3000 and http://127.0.0.1:3000 from the "
        "deployed CORS_ORIGINS before shipping, or the allowlist becomes a CSRF "
        "path. See the comment above this test."
    )


def test_the_app_sets_no_authentication_cookie() -> None:
    """The only cookie `app/` may set is the console's UI-mode hint.

    Scanned from source rather than exercised through a client: a cookie added
    on any route, including one no test happens to call, has the same effect on
    the CORS reasoning.
    """
    import ast
    import pathlib

    root = pathlib.Path(__file__).parent / "app"
    found: set[str] = set()
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not (isinstance(func, ast.Attribute) and func.attr == "set_cookie"):
                continue
            name = None
            if node.args and isinstance(node.args[0], ast.Constant):
                name = node.args[0].value
            for keyword in node.keywords:
                if keyword.arg == "key" and isinstance(keyword.value, ast.Constant):
                    name = keyword.value.value
            found.add(name if isinstance(name, str) else f"<dynamic in {path.name}>")

    assert found == {"devon_host"}, (
        f"app/ sets these cookies: {sorted(found)}. Only 'devon_host', the "
        "console's UI-mode hint, is expected. A new cookie is fine unless it "
        "carries authentication: an auth cookie is sent by the browser "
        "automatically, which turns every entry in the deployed CORS allowlist "
        "into ambient authority and makes the loopback entries a CSRF path. "
        "Either keep auth in the Authorization header, or drop the loopback "
        "origins from the production CORS_ORIGINS. See the comment above "
        "test_auth_is_a_bearer_header_so_allowlisted_origins_gain_no_ambient_authority."
    )

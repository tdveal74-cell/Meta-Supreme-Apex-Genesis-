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

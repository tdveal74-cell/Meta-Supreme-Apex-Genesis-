"""What the CORS allowlist will actually accept, said out loud at startup.

Written on 2026-08-27 after a production outage that took HTTP log forensics
to diagnose. Every browser call from the Command Center failed, the API logged
200s for the reads and 400s for the preflights, and nothing anywhere said which
origins the process would accept. The answer was that the front end's hostname
was not among them.

Two failure shapes are worth naming rather than leaving to inference.

An entry a browser Origin header can never equal is worse than a missing entry,
because it looks correct in the dashboard. A browser sends `scheme://host[:port]`
and nothing else, so a trailing slash, a path, or a stray space produces a value
that is present, plausible, and dead. Starlette compares origins by exact string
equality, so there is no near miss.

An allowlist that is entirely loopback on a deployed API means no deployed front
end can call it at all. That is never intended, and it is the exact state that
caused the outage.

These helpers are pure so they can be tested without booting the app; `app.main`
logs what they return.
"""

from __future__ import annotations

from typing import Iterable, Sequence, Tuple

# Environments where a loopback-only allowlist is the correct, expected setting.
LOCAL_ENVIRONMENTS = frozenset({"development", "test", "local"})

LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "0.0.0.0", "::1", "[::1]"})

Line = Tuple[str, str]  # (level, message); level is "info" or "warning"


def _host_of(origin: str) -> str:
    """The host of an origin, port removed. Empty when it cannot be read."""
    rest = origin.partition("://")[2]
    if not rest:
        return ""
    if rest.startswith("["):  # IPv6 literal, optionally followed by :port
        return rest.partition("]")[0] + "]"
    head, sep, tail = rest.rpartition(":")
    if sep and tail.isdigit():
        return head
    return rest


def is_malformed(origin: str) -> bool:
    """True when no browser Origin header can ever equal this string.

    `*` is excluded: Starlette reads it as allow-all rather than as a hostname,
    so it is a policy choice rather than a typo.
    """
    if origin == "*":
        return False
    if origin != origin.strip():
        return True
    scheme, sep, rest = origin.partition("://")
    if not sep or scheme not in ("http", "https"):
        return True
    # A path, a trailing slash, a query or a fragment: an Origin carries none.
    return rest == "" or any(mark in rest for mark in ("/", "?", "#"))


def malformed_origins(origins: Iterable[str]) -> Tuple[str, ...]:
    return tuple(origin for origin in origins if is_malformed(origin))


def is_localhost_only(origins: Sequence[str]) -> bool:
    """True when every usable entry points at this machine.

    Malformed entries are ignored rather than counted as remote: they match
    nothing, so an allowlist of one loopback entry plus one broken remote entry
    is still, in effect, loopback only.
    """
    usable = [origin for origin in origins if not is_malformed(origin)]
    if not usable:
        return True
    if any(origin == "*" for origin in usable):
        return False
    return all(_host_of(origin) in LOOPBACK_HOSTS for origin in usable)


def cors_startup_report(origins: Sequence[str], environment: str) -> Tuple[Line, ...]:
    """The lines `app.main` should log about the configured allowlist."""
    lines: list[Line] = []
    listed = ", ".join(origins) if origins else "(none)"
    lines.append(("info", f"CORS allows {len(origins)} origin(s): {listed}"))

    broken = malformed_origins(origins)
    if broken:
        lines.append(
            (
                "warning",
                "CORS: these entries can never match a browser Origin header "
                "(a trailing slash, path or stray space makes them dead on "
                f"arrival): {', '.join(repr(origin) for origin in broken)}",
            )
        )

    deployed = environment.strip().lower() not in LOCAL_ENVIRONMENTS
    if deployed and is_localhost_only(origins):
        lines.append(
            (
                "warning",
                f"CORS: ENVIRONMENT={environment} but every usable origin is "
                "loopback, so no deployed front end can call this API. Browser "
                "preflights will fail with 400 Disallowed CORS origin and reads "
                "will be blocked after returning 200.",
            )
        )
    return tuple(lines)


def log_cors_configuration(log, origins: Sequence[str], environment: str) -> None:
    """Emit the report through `log`, warnings as warnings.

    Kept here rather than inlined at the call site so the wiring itself is
    testable: a report nobody logs is exactly the silence this module exists to
    end.
    """
    for level, message in cors_startup_report(origins, environment):
        if level == "warning":
            log.warning(message)
        else:
            log.info(message)

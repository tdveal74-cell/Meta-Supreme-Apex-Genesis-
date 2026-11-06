"""Optional real HTTP fetcher for browser.fetch.

Used only when explicitly injected. CI and default registry keep the offline
stub so tests never depend on the network.
"""

from __future__ import annotations

from typing import Optional

import httpx

MAX_RESPONSE_BYTES = 200_000
MAX_TEXT_CHARS = 50_000


class ReadRateLimited(RuntimeError):
    """A read was throttled; this observation does not authorize a retry."""

    def __init__(self, retry_after: Optional[str] = None) -> None:
        self.retry_after_seconds: Optional[int] = None
        # Accept only bounded delta-seconds. Do not pass arbitrary header text
        # into tool output, or turn an advisory into permission to replay.
        if retry_after and retry_after.isascii() and retry_after.isdecimal():
            if len(retry_after) <= 5 and int(retry_after) <= 86400:
                self.retry_after_seconds = int(retry_after)
        super().__init__("HTTP 429: read rate limited; no automatic retry was performed")


class RedirectRefused(RuntimeError):
    """The allowlisted host answered with a redirect; the hop is not followed."""


def http_get_text(
    url: str,
    *,
    timeout_seconds: float = 15.0,
    transport: Optional[httpx.BaseTransport] = None,
) -> str:
    """GET one URL and return response text (truncated).

    Redirects are never followed. The adapter validated this URL's host
    against the allowlist; a redirect would hand the model the body of a
    host nobody validated (a metadata service, a database port on
    localhost). The refusal names the location so the model can ask for
    that URL explicitly, where the allowlist judges it.
    """
    with httpx.Client(
        timeout=timeout_seconds, follow_redirects=False, transport=transport
    ) as client, client.stream(
        "GET",
        url,
        headers={
            "User-Agent": "DEVON-BrowserAdapter/1.0",
            "Accept-Encoding": "identity",
        },
    ) as response:
        if 300 <= response.status_code < 400 and "location" in response.headers:
            location = response.headers.get("location", "")
            raise RedirectRefused(
                f"{url} answered {response.status_code} with a redirect to "
                f"{location or 'an unstated location'}; redirects are not followed. "
                "Fetch the destination explicitly if its host is allowlisted."
            )
        if response.status_code == 429:
            raise ReadRateLimited(response.headers.get("retry-after"))
        response.raise_for_status()
        # Bound the read before buffering, not after response.text has read the
        # entire page. Refuse compression rather than letting a small wire body
        # expand without a bound in HTTPX's decompressor.
        encoding = response.headers.get("content-encoding", "identity").strip().lower()
        if encoding not in {"", "identity"}:
            raise ValueError("compressed browser response refused; identity encoding required")
        body = bytearray()
        for chunk in response.iter_bytes(chunk_size=4096):
            body.extend(chunk[: MAX_RESPONSE_BYTES - len(body)])
            if len(body) == MAX_RESPONSE_BYTES:
                break
        try:
            text = body.decode(response.encoding or "utf-8", errors="replace")
        except LookupError:
            text = body.decode("utf-8", errors="replace")
        return text[:MAX_TEXT_CHARS]


def maybe_live_fetcher(enabled: bool) -> Optional[object]:
    """Return the live fetcher when enabled, else None (offline stub)."""
    if not enabled:
        return None
    return http_get_text

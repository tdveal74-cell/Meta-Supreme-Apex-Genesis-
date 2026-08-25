"""Optional real HTTP fetcher for browser.fetch.

Used only when explicitly injected. CI and default registry keep the offline
stub so tests never depend on the network.
"""

from __future__ import annotations

from typing import Optional

import httpx


def http_get_text(url: str, *, timeout_seconds: float = 15.0) -> str:
    """GET one URL and return response text (truncated)."""
    with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
        response = client.get(
            url,
            headers={"User-Agent": "DEVON-BrowserAdapter/1.0"},
        )
        response.raise_for_status()
        return response.text[:50_000]


def maybe_live_fetcher(enabled: bool) -> Optional[object]:
    """Return the live fetcher when enabled, else None (offline stub)."""
    if not enabled:
        return None
    return http_get_text

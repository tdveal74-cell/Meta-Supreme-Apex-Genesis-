"""Fix PR 5 from the DEVON and Hermes audit, H5: browser fetch redirects.

The live fetcher followed redirects, so an allowlisted host answering 302
to a metadata service or a localhost port handed that body to the model as
a READ result with the original URL in the metadata. Userinfo in a URL was
forwarded as a Basic Authorization header. Redirects are now refused with
the location named, credentials in a URL are refused before any request,
and the metadata records the URL actually read.
"""

from __future__ import annotations

import httpx
import pytest

from services.browser.agent_adapter import BrowserCapabilityAdapter
from services.browser.http_fetcher import RedirectRefused, http_get_text
from services.devon.approval import ApprovalQueue


def _transport(status: int, *, location: str = "", body: str = "ok") -> httpx.MockTransport:
    seen: list = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        headers = {"location": location} if location else {}
        return httpx.Response(status, headers=headers, text=body)

    transport = httpx.MockTransport(handler)
    transport.seen = seen  # type: ignore[attr-defined]
    return transport


def test_a_redirect_off_the_allowlist_is_not_followed():
    transport = _transport(302, location="http://169.254.169.254/latest/meta-data/")
    with pytest.raises(RedirectRefused) as caught:
        http_get_text("https://github.com/tdveal74-cell", transport=transport)
    assert "169.254.169.254" in str(caught.value)
    assert "not followed" in str(caught.value)
    assert len(transport.seen) == 1, "only the validated URL was requested"


def test_a_plain_page_still_reads():
    transport = _transport(200, body="<html>fine</html>")
    assert http_get_text("https://github.com/tdveal74-cell", transport=transport) == "<html>fine</html>"


def test_the_adapter_reports_the_refusal_as_a_failed_read():
    transport = _transport(301, location="http://localhost:5432/")

    def fetcher(url: str) -> str:
        return http_get_text(url, transport=transport)

    adapter = BrowserCapabilityAdapter(ApprovalQueue(), fetcher=fetcher)
    result = adapter._fetch({"url": "https://github.com/tdveal74-cell"})
    assert not result.ok
    assert "localhost:5432" in (result.error or "")


def test_credentials_in_the_url_are_refused_before_any_request():
    adapter = BrowserCapabilityAdapter(ApprovalQueue())
    result = adapter._fetch({"url": "https://tee:secret@github.com/tdveal74-cell"})
    assert not result.ok
    assert "credentials" in (result.error or "")
    result = adapter._navigate({"url": "https://tee:secret@github.com/tdveal74-cell"})
    assert not result.ok


def test_fetch_metadata_names_the_page_actually_read():
    adapter = BrowserCapabilityAdapter(ApprovalQueue())
    result = adapter._fetch({"url": "https://github.com/tdveal74-cell"})
    assert result.ok
    assert result.metadata["final_url"] == result.metadata["url"] == "https://github.com/tdveal74-cell"

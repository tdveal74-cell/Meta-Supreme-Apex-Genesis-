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
    # navigate checks its approval binding before the URL, so the URL rule
    # is exercised directly: an empty username is still credentials.
    for url in ("https://tee:secret@github.com/x", "https://@github.com/x", "https://:pw@github.com/x"):
        with pytest.raises(ValueError, match="credentials"):
            adapter._require_url(url)


def test_fetch_metadata_names_the_page_actually_read():
    adapter = BrowserCapabilityAdapter(ApprovalQueue())
    result = adapter._fetch({"url": "https://github.com/tdveal74-cell"})
    assert result.ok
    assert result.metadata["final_url"] == result.metadata["url"] == "https://github.com/tdveal74-cell"


@pytest.mark.parametrize("retry_after, expected", [
    ("15", 15), ("0", 0), ("86400", 86400), ("86401", None),
    ("-1", None), ("NaN", None), ("1.5", None), ("9" * 10000, None),
    ("Wed, 21 Oct 2026 07:28:00 GMT", None), ("", None),
])
def test_rate_limited_read_is_structured_without_automatic_replay(retry_after, expected):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(429, headers={"retry-after": retry_after}, text="private provider body")

    transport = httpx.MockTransport(handler)
    adapter = BrowserCapabilityAdapter(
        ApprovalQueue(), fetcher=lambda url: http_get_text(url, transport=transport),
    )
    result = adapter._fetch({"url": "https://github.com/tdveal74-cell"})
    assert not result.ok
    assert result.metadata == {
        "http_status": 429, "rate_limited": True,
        **({"retry_after_seconds": expected} if expected is not None else {}),
    }
    assert "no automatic retry" in result.error
    assert "private provider body" not in result.error
    assert "provider_receipt_id" not in result.metadata
    assert len(seen) == 1


def test_large_page_stops_reading_and_closes_the_stream():
    class LargePage(httpx.SyncByteStream):
        def __init__(self):
            self.bytes_read = 0
            self.closed = False

        def __iter__(self):
            for _ in range(1000):
                self.bytes_read += 4096
                yield b"x" * 4096

        def close(self):
            self.closed = True

    page = LargePage()
    seen = []

    def receive(request):
        seen.append(request)
        return httpx.Response(200, stream=page)

    text = http_get_text("https://github.com/", transport=httpx.MockTransport(receive))
    assert text == "x" * 50_000
    assert 200_000 <= page.bytes_read <= 204_096
    assert page.closed
    assert len(seen) == 1
    assert seen[0].headers["accept-encoding"] == "identity"


@pytest.mark.parametrize("content_encoding", ["gzip", "br", "deflate", "gzip, identity"])
def test_compression_is_refused_before_reading_or_expanding(content_encoding):
    class Unreadable(httpx.SyncByteStream):
        closed = False

        def __iter__(self):
            raise AssertionError("compressed bytes must not be read")
            yield b""  # pragma: no cover

        def close(self):
            self.closed = True

    page = Unreadable()
    transport = httpx.MockTransport(
        lambda _: httpx.Response(200, headers={"content-encoding": content_encoding}, stream=page)
    )
    with pytest.raises(ValueError, match="compressed browser response refused"):
        http_get_text("https://github.com/", transport=transport)
    assert page.closed


@pytest.mark.parametrize("charset,body,expected", [
    ("utf-8", "caf\u00e9".encode(), "caf\u00e9"),
    ("iso-8859-1", b"caf\xe9", "caf\u00e9"),
    ("invalid-charset", b"hello", "hello"),
])
def test_bounded_page_preserves_declared_encoding(charset, body, expected):
    transport = httpx.MockTransport(
        lambda _: httpx.Response(
            200, headers={"content-type": "text/html; charset=" + charset}, content=body
        )
    )
    assert http_get_text("https://github.com/", transport=transport) == expected

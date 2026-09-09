"""
The usage read route: what the control plane's cost panel is allowed to show.

Migration 017 has metered spend and refused at a cap since it landed, but
nothing read the ledger back. These tests pin the read: that it is read only,
that it is scoped to the caller, that a fresh account reads as a real zero
rather than a failure, and that the cap it reports is the same number the
refusal enforces rather than a second copy that can drift.
"""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.services.provider_usage import record_usage, utc_today

pytestmark = pytest.mark.asyncio


async def _me(client, headers) -> str:
    response = await client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 200, response.text
    return str(response.json()["id"])


async def test_an_account_with_no_calls_reads_a_real_zero(client, auth_headers):
    """Zero is a measurement here. A failure is an HTTP error, so a client can
    tell an account that spent nothing from a read that did not happen."""
    response = await client.get("/api/v1/usage", headers=auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["calls"] == 0
    assert body["tokens"] == 0
    assert body["input_tokens"] == 0
    assert body["output_tokens"] == 0
    assert body["date"] == utc_today().isoformat()


async def test_recorded_spend_comes_back_summed(client, auth_headers):
    user_id = await _me(client, auth_headers)
    await record_usage(user_id, input_tokens=120, output_tokens=80)
    await record_usage(user_id, input_tokens=5, output_tokens=15)

    body = (await client.get("/api/v1/usage", headers=auth_headers)).json()
    assert body["calls"] == 2
    assert body["input_tokens"] == 125
    assert body["output_tokens"] == 95
    assert body["tokens"] == 220


async def test_one_account_never_sees_another_accounts_spend(client, auth_headers):
    """The ledger keys on the account, and the route must never widen that."""
    user_id = await _me(client, auth_headers)
    await record_usage("some-other-account", input_tokens=999_999, output_tokens=0)
    await record_usage(user_id, input_tokens=10, output_tokens=0)

    body = (await client.get("/api/v1/usage", headers=auth_headers)).json()
    assert body["tokens"] == 10, "another account's spend leaked into this read"


async def test_the_reported_cap_is_the_one_the_refusal_reads(
    client, auth_headers, monkeypatch
):
    """A second copy of the cap would drift from the enforced one, and the
    panel would then reassure a reader who was about to be refused."""
    monkeypatch.setattr(settings, "PROVIDER_DAILY_TOKEN_CAP", 1_234)
    user_id = await _me(client, auth_headers)
    await record_usage(user_id, input_tokens=200, output_tokens=34)

    body = (await client.get("/api/v1/usage", headers=auth_headers)).json()
    assert body["cap_tokens"] == 1_234
    assert body["remaining_tokens"] == 1_000


async def test_no_cap_configured_reports_no_cap_rather_than_zero(
    client, auth_headers, monkeypatch
):
    """Zero would render as a cap of zero, which reads as everything refused."""
    monkeypatch.setattr(settings, "PROVIDER_DAILY_TOKEN_CAP", 0)
    body = (await client.get("/api/v1/usage", headers=auth_headers)).json()
    assert body["cap_tokens"] is None
    assert body["remaining_tokens"] is None


async def test_remaining_never_goes_negative(client, auth_headers, monkeypatch):
    """Past the cap the route reports no headroom, not a negative number that
    a progress bar would render as a reversed or overflowing fill."""
    monkeypatch.setattr(settings, "PROVIDER_DAILY_TOKEN_CAP", 100)
    user_id = await _me(client, auth_headers)
    await record_usage(user_id, input_tokens=500, output_tokens=0)

    body = (await client.get("/api/v1/usage", headers=auth_headers)).json()
    assert body["tokens"] == 500
    assert body["remaining_tokens"] == 0


async def test_the_route_says_a_provider_breakdown_is_unavailable(client, auth_headers):
    """The 017 ledger has no provider column. The route reports the dimension
    as unavailable so a client cannot mistake its absence for zero spend."""
    body = (await client.get("/api/v1/usage", headers=auth_headers)).json()
    assert body["providers_available"] is False
    assert "providers" not in body


async def test_usage_is_read_only_on_the_surface():
    """A spend ledger a client could write is not a ledger."""
    from app.main import app

    paths = app.openapi()["paths"]
    usage = {path: spec for path, spec in paths.items() if path.startswith("/api/v1/usage")}
    assert usage, "the usage route is not in the schema at all"
    for path, spec in usage.items():
        methods = {m.lower() for m in spec} & {"post", "put", "patch", "delete"}
        assert not methods, f"{path} exposes {sorted(methods)}"


async def test_the_route_refuses_an_unauthenticated_read(client):
    response = await client.get("/api/v1/usage")
    assert response.status_code in (401, 403), response.text

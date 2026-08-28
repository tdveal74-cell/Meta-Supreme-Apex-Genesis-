"""Integration tests for DEVON Command Center WebAuthn ceremonies."""

from app.core.config import settings


async def test_passkey_status_starts_empty(client, auth_headers):
    response = await client.get("/api/v1/auth/passkeys/status", headers=auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["available"] is False
    assert body["credentials"] == 0
    assert body["rp_id"] == settings.PASSKEY_RP_ID


async def test_passkey_registration_options_require_auth(client):
    response = await client.post("/api/v1/auth/passkeys/register/options")
    assert response.status_code == 401


async def test_passkey_registration_options_are_discoverable_and_verified(client, auth_headers):
    response = await client.post(
        "/api/v1/auth/passkeys/register/options", headers=auth_headers
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["challenge_id"]
    options = body["publicKey"]
    assert options["rp"]["id"] == settings.PASSKEY_RP_ID
    assert options["challenge"]
    assert options["authenticatorSelection"]["residentKey"] == "required"
    assert options["authenticatorSelection"]["userVerification"] == "required"


async def test_passkey_login_options_need_no_password_or_email(client):
    response = await client.post("/api/v1/auth/passkeys/login/options")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["challenge_id"]
    options = body["publicKey"]
    assert options["rpId"] == settings.PASSKEY_RP_ID
    assert options["userVerification"] == "required"
    assert options["challenge"]


def test_passkey_defaults_name_one_live_host():
    """The default rp id and origin must name the same, existing host.

    Pinned here rather than in each ceremony test, which assert the wiring
    instead: that every endpoint reports whatever host is configured. A literal
    repeated across three ceremonies pins the value in three places and tests
    the plumbing in none.

    The host matters because a WebAuthn credential is bound to the rp id. A
    default naming a retired project applies exactly when the deployment
    override is missing, and presents as a rejected passkey rather than as
    missing configuration.
    """
    assert settings.PASSKEY_RP_ID == "meta-supreme-apex-genesis-web.vercel.app"
    assert settings.PASSKEY_ORIGIN == f"https://{settings.PASSKEY_RP_ID}"

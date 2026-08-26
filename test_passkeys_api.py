"""Integration tests for DEVON Command Center WebAuthn ceremonies."""


async def test_passkey_status_starts_empty(client, auth_headers):
    response = await client.get("/api/v1/auth/passkeys/status", headers=auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["available"] is False
    assert body["credentials"] == 0
    assert body["rp_id"] == "meta-supreme-web.vercel.app"


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
    assert options["rp"]["id"] == "meta-supreme-web.vercel.app"
    assert options["challenge"]
    assert options["authenticatorSelection"]["residentKey"] == "required"
    assert options["authenticatorSelection"]["userVerification"] == "required"


async def test_passkey_login_options_need_no_password_or_email(client):
    response = await client.post("/api/v1/auth/passkeys/login/options")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["challenge_id"]
    options = body["publicKey"]
    assert options["rpId"] == "meta-supreme-web.vercel.app"
    assert options["userVerification"] == "required"
    assert options["challenge"]

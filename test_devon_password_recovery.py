"""Password recovery: an out-of-band key, because this API sends no email.

The estate had register, login and passkeys, and nothing between them. A
forgotten password meant a permanently unreachable account, since nothing in
the API can send a link anywhere. Tee hit exactly that on 2026-08-27.

The design borrows the Operator Bridge's trust boundary rather than inventing
one: a secret held in the deployment environment, readable only by whoever owns
the deployment. That is a real boundary here because DEVON is a single-operator
estate, and it needs no SMTP, no queue, and nothing that cannot run in CI.

Most of these tests are about the endpoint refusing. A reset endpoint is a
credential-replacement surface hanging off an unauthenticated route, so what it
declines to do carries more weight than what it does. The ordering test in
particular is the one that would matter under attack: the key is verified
before the account is touched, so the endpoint says nothing about who has an
account until the caller has proved they hold the secret.
"""

from __future__ import annotations

import pytest

from app.api.v1.auth import MIN_RECOVERY_KEY_LENGTH

# Long enough to satisfy the minimum, and obviously fake.
KEY = "recovery-key-for-tests-0123456789abcdef"
ACCOUNT = "recovery-subject@example.com"
FIRST_PASSWORD = "original-password-1"
NEW_PASSWORD = "replacement-password-2"


@pytest.fixture
def recovery_key(monkeypatch):
    monkeypatch.setenv("DEVON_RECOVERY_KEY", KEY)
    monkeypatch.delenv("DEVON_RECOVERY_EMAIL", raising=False)
    return KEY


async def make_account(client, email: str = ACCOUNT, password: str = FIRST_PASSWORD):
    created = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": password}
    )
    assert created.status_code in (201, 409), created.text
    return email


async def can_log_in(client, email: str, password: str) -> bool:
    response = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    return response.status_code == 200


# ---------------------------------------------------------------------------
# The path out of a lockout
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_recovery_key_replaces_a_forgotten_password(client, recovery_key):
    await make_account(client)
    assert await can_log_in(client, ACCOUNT, FIRST_PASSWORD)

    reset = await client.post(
        "/api/v1/auth/password/reset",
        json={"email": ACCOUNT, "new_password": NEW_PASSWORD, "recovery_key": recovery_key},
    )
    assert reset.status_code == 200, reset.text
    assert reset.json()["email"] == ACCOUNT

    assert await can_log_in(client, ACCOUNT, NEW_PASSWORD)
    assert not await can_log_in(client, ACCOUNT, FIRST_PASSWORD)


@pytest.mark.asyncio
async def test_recovery_re_enables_a_disabled_account(client, recovery_key, db_session):
    """Being locked out is the situation this endpoint exists to end."""
    from sqlalchemy import select

    from app.models.user import User

    await make_account(client)
    row = await db_session.execute(select(User).where(User.email == ACCOUNT))
    user = row.scalar_one()
    user.is_active = False
    await db_session.commit()

    assert not await can_log_in(client, ACCOUNT, FIRST_PASSWORD)

    reset = await client.post(
        "/api/v1/auth/password/reset",
        json={"email": ACCOUNT, "new_password": NEW_PASSWORD, "recovery_key": recovery_key},
    )
    assert reset.status_code == 200, reset.text
    assert await can_log_in(client, ACCOUNT, NEW_PASSWORD)


@pytest.mark.asyncio
async def test_the_key_stays_usable_for_a_second_recovery(client, recovery_key):
    """Unlike an emailed token, the key is a standing credential, not single use.

    Worth pinning: someone reading the code might assume reset semantics match
    the one-shot approval tokens elsewhere in this estate. They do not, and
    should not, or a second lockout would be unrecoverable.
    """
    await make_account(client)
    for password in ("first-replacement-1", "second-replacement-2"):
        reset = await client.post(
            "/api/v1/auth/password/reset",
            json={"email": ACCOUNT, "new_password": password, "recovery_key": recovery_key},
        )
        assert reset.status_code == 200, reset.text
        assert await can_log_in(client, ACCOUNT, password)


# ---------------------------------------------------------------------------
# What it refuses
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_an_unconfigured_deployment_has_no_reset_path_at_all(client, monkeypatch):
    """Fail closed. No key set must mean no endpoint, not an endpoint open to ''."""
    monkeypatch.delenv("DEVON_RECOVERY_KEY", raising=False)
    await make_account(client)

    # A syntactically valid key, so the request reaches the handler rather than
    # stopping at schema validation. An empty string never gets that far, which
    # is why it would not exercise the branch this test is about.
    reset = await client.post(
        "/api/v1/auth/password/reset",
        json={
            "email": ACCOUNT,
            "new_password": NEW_PASSWORD,
            "recovery_key": "any-key-at-all-of-sufficient-length-here",
        },
    )
    assert reset.status_code == 503
    assert "not configured" in reset.json()["detail"]
    assert await can_log_in(client, ACCOUNT, FIRST_PASSWORD)


@pytest.mark.asyncio
async def test_a_short_key_is_refused_as_if_unconfigured(client, monkeypatch):
    """The realistic attack is a human choosing something short, not brute force."""
    monkeypatch.setenv("DEVON_RECOVERY_KEY", "devon123")
    await make_account(client)

    reset = await client.post(
        "/api/v1/auth/password/reset",
        json={"email": ACCOUNT, "new_password": NEW_PASSWORD, "recovery_key": "devon123"},
    )
    assert reset.status_code == 503
    assert str(MIN_RECOVERY_KEY_LENGTH) in reset.json()["detail"]
    assert await can_log_in(client, ACCOUNT, FIRST_PASSWORD)


@pytest.mark.asyncio
async def test_a_wrong_key_changes_nothing(client, recovery_key):
    await make_account(client)

    reset = await client.post(
        "/api/v1/auth/password/reset",
        json={
            "email": ACCOUNT,
            "new_password": NEW_PASSWORD,
            "recovery_key": "wrong-key-of-entirely-sufficient-length-x",
        },
    )
    assert reset.status_code == 403
    assert await can_log_in(client, ACCOUNT, FIRST_PASSWORD)
    assert not await can_log_in(client, ACCOUNT, NEW_PASSWORD)


@pytest.mark.asyncio
async def test_the_key_is_checked_before_the_account_is_looked_up(client, recovery_key):
    """The property that keeps this endpoint from being a user directory.

    A caller without the key gets the same 403 for an account that exists and
    one that does not. If the lookup ran first, the endpoint would answer "does
    tee@example.com have an account here" to anyone who asked.
    """
    await make_account(client)

    real = await client.post(
        "/api/v1/auth/password/reset",
        json={"email": ACCOUNT, "new_password": NEW_PASSWORD, "recovery_key": "bad-key-but-long-enough-to-pass-length"},
    )
    absent = await client.post(
        "/api/v1/auth/password/reset",
        json={
            "email": "nobody-has-this-address@example.com",
            "new_password": NEW_PASSWORD,
            "recovery_key": "bad-key-but-long-enough-to-pass-length",
        },
    )

    assert real.status_code == absent.status_code == 403
    assert real.json()["detail"] == absent.json()["detail"]


@pytest.mark.asyncio
async def test_a_correct_key_may_speak_plainly_about_a_missing_account(client, recovery_key):
    """Once the secret is proved, hiding the reason only wastes the operator's time."""
    reset = await client.post(
        "/api/v1/auth/password/reset",
        json={
            "email": "nobody-has-this-address@example.com",
            "new_password": NEW_PASSWORD,
            "recovery_key": recovery_key,
        },
    )
    assert reset.status_code == 404
    assert "No account" in reset.json()["detail"]


@pytest.mark.asyncio
async def test_a_short_new_password_is_rejected_by_the_same_rule_as_register(
    client, recovery_key
):
    await make_account(client)
    reset = await client.post(
        "/api/v1/auth/password/reset",
        json={"email": ACCOUNT, "new_password": "short", "recovery_key": recovery_key},
    )
    assert reset.status_code == 422
    assert await can_log_in(client, ACCOUNT, FIRST_PASSWORD)


# ---------------------------------------------------------------------------
# The optional pin
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_pin_confines_the_key_to_one_account(client, recovery_key, monkeypatch):
    """A leaked key should not be a skeleton key for every account on the box."""
    monkeypatch.setenv("DEVON_RECOVERY_EMAIL", ACCOUNT)
    other = await make_account(client, "someone-else@example.com", FIRST_PASSWORD)

    reset = await client.post(
        "/api/v1/auth/password/reset",
        json={"email": other, "new_password": NEW_PASSWORD, "recovery_key": recovery_key},
    )
    assert reset.status_code == 403
    assert "does not cover" in reset.json()["detail"]
    assert await can_log_in(client, other, FIRST_PASSWORD)


@pytest.mark.asyncio
async def test_the_pinned_account_still_recovers(client, recovery_key, monkeypatch):
    monkeypatch.setenv("DEVON_RECOVERY_EMAIL", ACCOUNT.upper())
    await make_account(client)

    reset = await client.post(
        "/api/v1/auth/password/reset",
        json={"email": ACCOUNT, "new_password": NEW_PASSWORD, "recovery_key": recovery_key},
    )
    assert reset.status_code == 200, reset.text
    assert await can_log_in(client, ACCOUNT, NEW_PASSWORD)

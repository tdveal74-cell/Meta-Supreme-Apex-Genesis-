"""
Authentication endpoints.
Supports password registration/login plus WebAuthn passkeys for the DEVON
Command Center. Password remains a recovery path; passkey login issues the same
JWT used everywhere else so authorization semantics do not fork.
"""

from __future__ import annotations

import hmac
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from webauthn import (
    base64url_to_bytes,
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import bytes_to_base64url
from webauthn.helpers.exceptions import (
    InvalidAuthenticationResponse,
    InvalidRegistrationResponse,
)
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from app.core.config import settings
from app.db.session import get_db
from app.models.passkey import PasskeyChallenge, PasskeyCredential
from app.models.user import User
from app.security.deps import CurrentUser
from app.security.jwt import create_access_token
from app.security.password import hash_password, verify_password

#: A recovery key shorter than this is refused outright. The realistic threat
#: is not brute force against a random secret, it is a human picking something
#: short and memorable for a credential that resets an account.
MIN_RECOVERY_KEY_LENGTH = 32

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str | None = Field(None, max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class PasswordResetRequest(BaseModel):
    email: EmailStr
    new_password: str = Field(..., min_length=8, max_length=128)
    recovery_key: str = Field(..., min_length=1, max_length=512)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str | None = None
    is_verified: bool = False
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class PasskeyCeremonyResponse(BaseModel):
    challenge_id: str
    publicKey: dict[str, Any]


class PasskeyRegistrationComplete(BaseModel):
    challenge_id: str = Field(..., min_length=8, max_length=128)
    credential: dict[str, Any]
    label: str = Field("DEVON passkey", min_length=1, max_length=120)


class PasskeyAuthenticationComplete(BaseModel):
    challenge_id: str = Field(..., min_length=8, max_length=128)
    credential: dict[str, Any]


class PasskeyStatusResponse(BaseModel):
    available: bool
    credentials: int
    rp_id: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _token_for(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(subject=str(user.id)),
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


def _user_handle(user_id: str) -> bytes:
    """Stable opaque WebAuthn user handle from the existing UUID."""
    return bytes.fromhex(user_id.replace("-", ""))


def _new_challenge(*, kind: str, challenge: bytes, user_id: str | None) -> PasskeyChallenge:
    return PasskeyChallenge(
        id=secrets.token_urlsafe(24),
        challenge=bytes_to_base64url(challenge),
        kind=kind,
        user_id=user_id,
        expires_at=datetime.now(timezone.utc)
        + timedelta(seconds=settings.PASSKEY_CHALLENGE_TTL_SECONDS),
    )


async def _consume_challenge(
    db: AsyncSession,
    *,
    challenge_id: str,
    kind: str,
    user_id: str | None = None,
) -> PasskeyChallenge:
    result = await db.execute(
        select(PasskeyChallenge)
        .where(PasskeyChallenge.id == challenge_id)
        .with_for_update()
    )
    row = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if (
        row is None
        or row.kind != kind
        or row.used_at is not None
        or row.expires_at <= now
        or (user_id is not None and row.user_id != user_id)
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passkey challenge is missing, expired, or already used.",
        )
    return row


# ---------------------------------------------------------------------------
# Password endpoints
# ---------------------------------------------------------------------------

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user account."""
    existing = await db.execute(select(User).where(User.email == payload.email.lower()))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    user = User(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        is_active=True,
        is_verified=False,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate with password and return a JWT access token."""
    result = await db.execute(select(User).where(User.email == payload.email.lower()))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")

    user.last_login_at = datetime.now(timezone.utc)
    await db.flush()
    return _token_for(user)


@router.post("/password/reset", response_model=UserResponse)
async def reset_password(
    payload: PasswordResetRequest,
    db: AsyncSession = Depends(get_db),
):
    """Set a new password using the out-of-band recovery key.

    This API sends no email, so the usual emailed-link flow has nothing to send
    a link through. What exists instead is the trust boundary the Operator
    Bridge already relies on: a secret held in the deployment environment and
    readable only by whoever owns the deployment. Someone who can read
    DEVON_RECOVERY_KEY in Railway is, by construction, entitled to recover the
    account.

    Four properties make that safe to expose on a public endpoint.

    It fails closed when unconfigured. A deployment that never set the key has
    no reset path at all, rather than one guarded by an empty string. A key too
    short to resist guessing is refused for the same reason.

    The key is checked FIRST, before the account is looked up. Every later error
    may speak plainly about whether an email exists, because reaching them means
    the caller already proved they hold the secret. A caller who has not proved
    it learns nothing here about who has an account.

    The comparison is constant time, so the key cannot be recovered a byte at a
    time from response timing.

    Passkeys deliberately survive a reset. Clearing them would turn a leaked
    recovery key into a way to strip the account's strongest credential, and
    anyone who passed the key check can already sign in regardless.

    One honest limit: JWTs already issued stay valid until they expire. Tokens
    are stateless and there is no denylist, so a reset closes off future logins
    with the old password without severing a session already in flight.
    """
    configured = os.getenv("DEVON_RECOVERY_KEY", "").strip()
    if len(configured) < MIN_RECOVERY_KEY_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Password recovery is not configured. Set DEVON_RECOVERY_KEY to a "
                f"random secret of at least {MIN_RECOVERY_KEY_LENGTH} characters."
            ),
        )

    if not hmac.compare_digest(configured, payload.recovery_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Recovery key is not valid.",
        )

    email = payload.email.lower()

    # Optional pin. When set, the key recovers exactly one account instead of
    # any account on the deployment, so a leaked key cannot take over a
    # different user. Cheap, and recommended.
    pinned = os.getenv("DEVON_RECOVERY_EMAIL", "").strip().lower()
    if pinned and not hmac.compare_digest(pinned, email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This recovery key does not cover that account.",
        )

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No account with that email.",
        )

    user.password_hash = hash_password(payload.new_password)
    # A disabled account is re-enabled by a successful recovery: being locked
    # out is the situation this endpoint exists to end.
    user.is_active = True
    await db.flush()
    await db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# Passkey registration: authenticated user binds a device credential once.
# ---------------------------------------------------------------------------

@router.post("/passkeys/register/options", response_model=PasskeyCeremonyResponse)
async def passkey_registration_options(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(
        select(PasskeyCredential).where(PasskeyCredential.user_id == current_user.id)
    )
    credentials = list(existing.scalars().all())
    options = generate_registration_options(
        rp_id=settings.PASSKEY_RP_ID,
        rp_name=settings.PASSKEY_RP_NAME,
        user_id=_user_handle(current_user.id),
        user_name=current_user.email,
        user_display_name=current_user.full_name or current_user.email,
        exclude_credentials=[
            PublicKeyCredentialDescriptor(id=base64url_to_bytes(item.credential_id))
            for item in credentials
        ],
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
    )
    challenge = _new_challenge(
        kind="registration", challenge=options.challenge, user_id=current_user.id
    )
    db.add(challenge)
    await db.flush()
    return PasskeyCeremonyResponse(
        challenge_id=challenge.id,
        publicKey=json.loads(options_to_json(options)),
    )


@router.post("/passkeys/register/complete")
async def passkey_registration_complete(
    payload: PasskeyRegistrationComplete,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    challenge = await _consume_challenge(
        db,
        challenge_id=payload.challenge_id,
        kind="registration",
        user_id=current_user.id,
    )
    try:
        verified = verify_registration_response(
            credential=payload.credential,
            expected_challenge=base64url_to_bytes(challenge.challenge),
            expected_origin=settings.PASSKEY_ORIGIN,
            expected_rp_id=settings.PASSKEY_RP_ID,
            require_user_verification=True,
        )
    except InvalidRegistrationResponse as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Passkey registration was rejected: {exc}",
        ) from exc

    credential_id = bytes_to_base64url(verified.credential_id)
    duplicate = await db.execute(
        select(PasskeyCredential).where(PasskeyCredential.credential_id == credential_id)
    )
    if duplicate.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="That passkey is already registered.")

    db.add(
        PasskeyCredential(
            credential_id=credential_id,
            user_id=current_user.id,
            credential_public_key=bytes_to_base64url(verified.credential_public_key),
            sign_count=verified.sign_count,
            label=payload.label.strip(),
        )
    )
    challenge.used_at = datetime.now(timezone.utc)
    await db.flush()
    return {"registered": True, "credential_id": credential_id}


# ---------------------------------------------------------------------------
# Passkey authentication: discoverable credential -> existing DEVON JWT.
# ---------------------------------------------------------------------------

@router.post("/passkeys/login/options", response_model=PasskeyCeremonyResponse)
async def passkey_login_options(db: AsyncSession = Depends(get_db)):
    options = generate_authentication_options(
        rp_id=settings.PASSKEY_RP_ID,
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    challenge = _new_challenge(kind="authentication", challenge=options.challenge, user_id=None)
    db.add(challenge)
    await db.flush()
    return PasskeyCeremonyResponse(
        challenge_id=challenge.id,
        publicKey=json.loads(options_to_json(options)),
    )


@router.post("/passkeys/login/complete", response_model=TokenResponse)
async def passkey_login_complete(
    payload: PasskeyAuthenticationComplete,
    db: AsyncSession = Depends(get_db),
):
    challenge = await _consume_challenge(
        db,
        challenge_id=payload.challenge_id,
        kind="authentication",
    )
    credential_id = str(payload.credential.get("id") or "")
    if not credential_id:
        raise HTTPException(status_code=400, detail="Passkey response is missing its credential ID.")

    found = await db.execute(
        select(PasskeyCredential, User)
        .join(User, User.id == PasskeyCredential.user_id)
        .where(PasskeyCredential.credential_id == credential_id)
        .with_for_update()
    )
    row = found.one_or_none()
    if row is None:
        raise HTTPException(status_code=401, detail="Passkey is not registered with DEVON.")
    stored, user = row
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    try:
        verified = verify_authentication_response(
            credential=payload.credential,
            expected_challenge=base64url_to_bytes(challenge.challenge),
            expected_rp_id=settings.PASSKEY_RP_ID,
            expected_origin=settings.PASSKEY_ORIGIN,
            credential_public_key=base64url_to_bytes(stored.credential_public_key),
            credential_current_sign_count=stored.sign_count,
            require_user_verification=True,
        )
    except InvalidAuthenticationResponse as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Passkey authentication was rejected: {exc}",
        ) from exc

    response_handle = payload.credential.get("response", {}).get("userHandle")
    if response_handle:
        try:
            if base64url_to_bytes(str(response_handle)) != _user_handle(user.id):
                raise HTTPException(status_code=401, detail="Passkey user handle does not match.")
        except ValueError as exc:
            raise HTTPException(status_code=401, detail="Passkey user handle is invalid.") from exc

    stored.sign_count = verified.new_sign_count
    stored.last_used_at = datetime.now(timezone.utc)
    user.last_login_at = stored.last_used_at
    challenge.used_at = stored.last_used_at
    await db.flush()
    return _token_for(user)


@router.get("/passkeys/status", response_model=PasskeyStatusResponse)
async def passkey_status(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PasskeyCredential).where(PasskeyCredential.user_id == current_user.id)
    )
    credentials = list(result.scalars().all())
    return PasskeyStatusResponse(
        available=bool(credentials),
        credentials=len(credentials),
        rp_id=settings.PASSKEY_RP_ID,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: CurrentUser):
    """Return the currently authenticated user."""
    return current_user

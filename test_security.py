"""Security utility tests."""

from datetime import timedelta

import jwt as pyjwt

from app.core.config import settings
from app.security.jwt import create_access_token, decode_access_token
from app.security.password import hash_password, verify_password


def test_password_hash_and_verify():
    password = "secure-password-123"
    hashed = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_jwt_roundtrip():
    token = create_access_token(subject="user-123")
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "user-123"
    assert payload["type"] == "access"


def test_jwt_expired_token_is_rejected():
    # A token whose exp is already in the past decodes to None, the same
    # outcome the caller sees for any other invalid token: get_current_user
    # (app/security/deps.py) turns this into 401 "Invalid or expired token".
    token = create_access_token(subject="user-123", expires_delta=timedelta(seconds=-1))
    assert decode_access_token(token) is None


def test_jwt_tampered_signature_is_rejected():
    # Flip a character in the signature segment so the payload no longer
    # matches what was signed. This must fail the same way an expired or
    # malformed token does: None, not an exception the caller has to catch.
    token = create_access_token(subject="user-123")
    header, payload, signature = token.split(".")
    tampered_char = "A" if signature[-1] != "A" else "B"
    tampered_signature = signature[:-1] + tampered_char
    tampered_token = f"{header}.{payload}.{tampered_signature}"
    assert decode_access_token(tampered_token) is None


def test_jwt_wrong_key_is_rejected():
    # A token signed with a different secret than the one decode_access_token
    # verifies against must fail closed, exactly like a tampered signature.
    other_key_token = pyjwt.encode(
        {"sub": "user-123", "type": "access"},
        "a-completely-different-secret-key-not-the-real-one",
        algorithm=settings.ALGORITHM,
    )
    assert decode_access_token(other_key_token) is None


def test_jwt_malformed_token_is_rejected():
    assert decode_access_token("not-a-jwt-at-all") is None

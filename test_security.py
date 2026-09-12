"""Security utility tests."""

import base64
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
    # Flip the first byte of the decoded signature so the payload no longer
    # matches what was signed. This must fail the same way an expired or
    # malformed token does: None, not an exception the caller has to catch.
    #
    # Substituting a character in the base64url text directly is not safe:
    # a 32-byte HMAC-SHA256 signature encodes to 43 base64url characters,
    # and the last character's two low bits are unused padding, so about
    # one signature in sixteen has a last character whose top four bits
    # already equal "A" or "B", making the substitution a no-op that
    # leaves the real signature bytes, and the test's own premise, intact.
    # Flipping a byte of the decoded signature has no such alignment case.
    token = create_access_token(subject="user-123")
    header, payload, signature = token.split(".")
    padded = signature + "=" * (-len(signature) % 4)
    raw = bytearray(base64.urlsafe_b64decode(padded))
    raw[0] ^= 0xFF
    tampered_signature = base64.urlsafe_b64encode(bytes(raw)).rstrip(b"=").decode()
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

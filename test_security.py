"""Security utility tests."""

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

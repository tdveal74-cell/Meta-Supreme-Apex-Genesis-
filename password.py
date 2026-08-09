"""Password hashing utilities.

Uses the `bcrypt` library directly (passlib is unmaintained and incompatible
with bcrypt >= 4.1). Hashes are standard `$2b$` bcrypt strings, fully
compatible with hashes previously produced via passlib.

Note: bcrypt operates on at most 72 bytes of input. Longer passwords are
explicitly truncated to 72 bytes (the same behavior passlib applied
silently), so existing credentials keep verifying identically.
"""

import bcrypt

_BCRYPT_MAX_BYTES = 72
_BCRYPT_ROUNDS = 12


def _prepare(password: str) -> bytes:
    """Encode and truncate a password to bcrypt's 72-byte input limit."""
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    """Hash a plain-text password."""
    salt = bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)
    return bcrypt.hashpw(_prepare(password), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a stored hash."""
    try:
        return bcrypt.checkpw(_prepare(plain_password), hashed_password.encode("utf-8"))
    except ValueError:
        # Malformed / non-bcrypt hash — never raise from a verify path.
        return False

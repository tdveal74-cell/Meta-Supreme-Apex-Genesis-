"""LiveKit join tokens minted with PyJWT: claim layout, signing, refusal."""

import time

import jwt
import pytest

from apps.presence.livekit_token import decode_livekit_token, mint_livekit_token

API_KEY = "APIabc123"
API_SECRET = "livekit-secret-for-tests-only-0123456789"


def test_claims_are_exactly_the_documented_layout():
    now = 1_800_000_000
    token = mint_livekit_token(
        API_KEY, API_SECRET, "user-1", "room-a", ttl_seconds=600, name="Tee", now=now
    )
    claims = jwt.decode(token, options={"verify_signature": False})

    assert set(claims) == {"iss", "sub", "nbf", "exp", "name", "video"}
    assert claims["iss"] == API_KEY
    assert claims["sub"] == "user-1"
    assert claims["nbf"] == now
    assert claims["exp"] == now + 600
    assert claims["name"] == "Tee"
    assert claims["video"] == {
        "room": "room-a",
        "roomJoin": True,
        "canPublish": True,
        "canSubscribe": True,
    }
    assert jwt.get_unverified_header(token)["alg"] == "HS256"


def test_decode_verifies_signature_issuer_and_time_claims():
    now = int(time.time())
    token = mint_livekit_token(API_KEY, API_SECRET, "user-2", "room-b", ttl_seconds=300, now=now)
    claims = decode_livekit_token(token, API_KEY, API_SECRET)
    assert claims["sub"] == "user-2"
    assert claims["video"]["room"] == "room-b"
    assert claims["exp"] - claims["nbf"] == 300


def test_wrong_secret_and_wrong_issuer_are_refused():
    token = mint_livekit_token(API_KEY, API_SECRET, "user-3", "room-c")
    with pytest.raises(jwt.InvalidSignatureError):
        decode_livekit_token(token, API_KEY, "not-the-secret-0123456789abcdef0123456789abcdef")
    with pytest.raises(jwt.InvalidIssuerError):
        decode_livekit_token(token, "APIother", API_SECRET)


def test_expired_token_is_refused():
    stale = int(time.time()) - 10_000
    token = mint_livekit_token(API_KEY, API_SECRET, "user-4", "room-d", ttl_seconds=60, now=stale)
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_livekit_token(token, API_KEY, API_SECRET)


def test_publish_and_subscribe_flags_carry_through():
    token = mint_livekit_token(
        API_KEY, API_SECRET, "viewer", "room-e", can_publish=False, can_subscribe=True
    )
    claims = decode_livekit_token(token, API_KEY, API_SECRET)
    assert claims["video"]["canPublish"] is False
    assert claims["video"]["canSubscribe"] is True
    assert claims["name"] == ""


def test_refuses_missing_inputs_by_name():
    with pytest.raises(ValueError, match="LIVEKIT_API_KEY and LIVEKIT_API_SECRET"):
        mint_livekit_token("", API_SECRET, "u", "r")
    with pytest.raises(ValueError, match="identity"):
        mint_livekit_token(API_KEY, API_SECRET, " ", "r")
    with pytest.raises(ValueError, match="room"):
        mint_livekit_token(API_KEY, API_SECRET, "u", "")
    with pytest.raises(ValueError, match="ttl_seconds"):
        mint_livekit_token(API_KEY, API_SECRET, "u", "r", ttl_seconds=0)

"""A lone surrogate in a JSON body is answered 422, not 500. Found 2026-10-14."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.core.json_guard import MAX_CHECKED_BYTES, body_has_lone_surrogate
from app.main import app

BS = chr(92)
LONE_HIGH = BS + "ud800"
LONE_LOW = BS + "udc00"
PAIR = BS + "ud83d" + BS + "ude00"  # U+1F600, a normal emoji
MESSAGE = "request body contains an unpaired surrogate character"
client = TestClient(app, raise_server_exceptions=False)


def post(path: str, raw: str, content_type: str = "application/json"):
    return client.post(path, content=raw.encode("ascii"), headers={"content-type": content_type})


@pytest.mark.parametrize("raw", [
    '{"a": "x' + LONE_HIGH + 'y"}',
    '{"a": "x' + LONE_LOW + 'y"}',
    '{"a": "' + LONE_LOW + LONE_HIGH + '"}',
    '{"x' + LONE_HIGH + '": 1}',
    '{"a": ["ok", {"b": "' + LONE_HIGH + '"}]}',
    '{"a": "' + LONE_HIGH + 'z' + LONE_LOW + '"}',
    '{"a": "' + BS + "uD800" + '"}',
])
def test_a_lone_surrogate_anywhere_is_found(raw):
    assert body_has_lone_surrogate(raw.encode("ascii"))


@pytest.mark.parametrize("raw", [
    '{"a": "plain"}',
    '{"a": "' + PAIR + '"}',
    '{"a": "' + BS + 'u00e9"}',
])
def test_clean_bodies_pass(raw):
    assert not body_has_lone_surrogate(raw.encode("ascii"))


def test_invalid_json_is_left_to_the_routes_own_decoder():
    assert not body_has_lone_surrogate(('{"a": "' + LONE_HIGH).encode("ascii"))


@pytest.mark.parametrize("path", ["/api/v1/auth/login", "/api/v1/auth/register"])
def test_the_live_app_answers_422_with_a_named_reason(path):
    r = post(path, '{"email": "a@x.com", "password": "' + LONE_HIGH + '", "full_name": "' + LONE_LOW + '"}')
    assert r.status_code == 422
    assert r.json()["detail"] == MESSAGE
    assert r.json()["error"]["code"] == "validation_error"


def test_a_valid_pair_is_not_refused_by_the_guard():
    r = post("/api/v1/auth/login", '{"email": "a@x.com", "password": "' + PAIR + '"}')
    assert r.json().get("detail") != MESSAGE


def test_the_body_reaches_the_route_intact_after_the_check():
    r = post("/api/v1/auth/login", json.dumps({"email": "not-an-email", "password": "x"}))
    assert r.status_code == 422
    assert r.json()["error"]["message"] != MESSAGE
    assert any("email" in str(e.get("loc")) for e in r.json()["error"]["details"])


def test_other_content_types_and_methods_are_untouched():
    r = post("/api/v1/auth/login", "email=a" + LONE_HIGH, content_type="text/plain")
    assert r.json().get("detail") != MESSAGE
    assert client.get("/api/v1/health").status_code == 200


def test_a_body_over_the_cap_is_not_parsed():
    big = '{"pad": "' + "a" * MAX_CHECKED_BYTES + '", "x": "' + LONE_HIGH + '"}'
    assert len(big) > MAX_CHECKED_BYTES
    r = post("/api/v1/auth/login", big)
    assert r.json().get("detail") != MESSAGE


RAW_LONE = bytes([0xED, 0xA0, 0x80])  # U+D800 as three raw UTF-8 bytes


@pytest.mark.parametrize("path", ["/api/v1/auth/login", "/api/v1/auth/register"])
@pytest.mark.parametrize("name,body", [
    ("raw utf-8 bytes", b'{"email": "' + RAW_LONE + b'", "password": "x"}'),
    ("raw bytes in a password", b'{"email": "a@x.com", "password": "' + RAW_LONE + b'"}'),
    ("utf-16 with the escape text", ('{"email": "' + LONE_HIGH + '", "password": "x"}').encode("utf-16")),
    ("utf-16-le with raw surrogate",
     '{"email": "'.encode("utf-16-le") + b"\x00\xd8" + '", "password": "x"}'.encode("utf-16-le")),
])
def test_a_surrogate_that_arrives_as_bytes_is_answered_422(path, name, body):
    r = client.post(path, content=body, headers={"content-type": "application/json"})
    assert r.status_code == 422, name
    assert r.json()["detail"] == MESSAGE


def test_ordinary_non_ascii_text_still_passes():
    text = '{"email": "a@x.com", "password": "caf' + chr(0xE9) + ' ' + chr(0x2603) + '"}'
    assert not body_has_lone_surrogate(text.encode("utf-8"))
    assert not body_has_lone_surrogate(text.encode("utf-16"))

"""Fix PR 4 from the DEVON and Hermes audit, H3: the public SECRET_KEY.

SECRET_KEY defaulted to a string anyone holding the repository can read,
and nothing refused to boot with it, so with the variable unset in
production a forged HS256 token for any user id verified. The process now
refuses to start when ENVIRONMENT is production and SECRET_KEY is the
default or empty, and the compose file no longer ships the literal.
"""

from __future__ import annotations

import pathlib

import pytest
from pydantic import ValidationError

from app.core.config import DEFAULT_SECRET_KEY, Settings, secret_key_refusal

REAL = "0f3a9c7e1b5d2a8f4c6e9b1d3a5f7c2e4b6d8a0c1e3f5b7d9a2c4e6f8b0d1a3c"


def test_production_refuses_the_default_and_an_empty_key():
    assert "public default" in secret_key_refusal("production", DEFAULT_SECRET_KEY)
    assert "empty" in secret_key_refusal("production", "")
    assert "empty" in secret_key_refusal("Production", "   ")
    assert secret_key_refusal("production", REAL) == ""


def test_other_environments_keep_the_default_for_offline_work():
    for environment in ("development", "test", "staging", ""):
        assert secret_key_refusal(environment, DEFAULT_SECRET_KEY) == ""


def test_settings_will_not_construct_for_production_with_the_default():
    with pytest.raises(ValidationError) as caught:
        Settings(_env_file=None, ENVIRONMENT="production", SECRET_KEY=DEFAULT_SECRET_KEY)
    assert "Refusing to start" in str(caught.value)

    ok = Settings(_env_file=None, ENVIRONMENT="production", SECRET_KEY=REAL)
    assert ok.SECRET_KEY == REAL
    dev = Settings(_env_file=None, ENVIRONMENT="development", SECRET_KEY=DEFAULT_SECRET_KEY)
    assert dev.SECRET_KEY == DEFAULT_SECRET_KEY


def test_compose_no_longer_ships_the_literal():
    compose = pathlib.Path(__file__).with_name("infrastructure") / "docker" / "docker-compose.yml"
    text = compose.read_text(encoding="utf-8")
    assert DEFAULT_SECRET_KEY not in text
    assert "${SECRET_KEY:?" in text

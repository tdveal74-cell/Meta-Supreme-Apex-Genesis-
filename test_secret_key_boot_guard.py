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

from app.core.config import (
    DEFAULT_SECRET_KEY,
    Settings,
    deployment_reason,
    secret_key_refusal,
)

REAL = "0f3a9c7e1b5d2a8f4c6e9b1d3a5f7c2e4b6d8a0c1e3f5b7d9a2c4e6f8b0d1a3c"


NO_PLATFORM: dict = {}


def test_production_refuses_the_default_and_an_empty_key():
    assert "public default" in secret_key_refusal("production", DEFAULT_SECRET_KEY, NO_PLATFORM)
    assert "empty" in secret_key_refusal("production", "", NO_PLATFORM)
    assert "empty" in secret_key_refusal("Production", "   ", NO_PLATFORM)
    assert secret_key_refusal("production", REAL, NO_PLATFORM) == ""


def test_every_deployed_environment_is_refused_the_default():
    """Staging is reachable and signs the same JWTs; only a developer's own
    machine keeps the default."""
    for environment in ("staging", "prod", "preview", "anything-else"):
        assert "public default" in secret_key_refusal(environment, DEFAULT_SECRET_KEY, NO_PLATFORM)
    for environment in ("development", "dev", "test", "local", ""):
        assert secret_key_refusal(environment, DEFAULT_SECRET_KEY, NO_PLATFORM) == ""


def test_a_hosting_platform_marker_means_deployed_whatever_environment_says():
    """A Railway service whose ENVIRONMENT was never set still runs on Railway,
    which injects its own variables into every deployment."""
    for marker in ("RAILWAY_ENVIRONMENT_NAME", "RAILWAY_PROJECT_ID", "VERCEL_ENV"):
        reason = deployment_reason("development", {marker: "production"})
        assert marker in reason
        assert "public default" in secret_key_refusal("development", DEFAULT_SECRET_KEY, {marker: "x"})
        assert secret_key_refusal("development", REAL, {marker: "x"}) == ""
    assert deployment_reason("development", {"RAILWAY_PROJECT_ID": "  "}) == ""


def test_settings_will_not_construct_for_production_with_the_default():
    with pytest.raises(ValidationError) as caught:
        Settings(_env_file=None, ENVIRONMENT="production", SECRET_KEY=DEFAULT_SECRET_KEY)
    assert "Refusing to start" in str(caught.value)

    ok = Settings(_env_file=None, ENVIRONMENT="production", SECRET_KEY=REAL)
    assert ok.SECRET_KEY == REAL
    dev = Settings(_env_file=None, ENVIRONMENT="development", SECRET_KEY=DEFAULT_SECRET_KEY)
    assert dev.SECRET_KEY == DEFAULT_SECRET_KEY


def test_settings_refuse_the_default_under_a_platform_marker(monkeypatch):
    monkeypatch.setenv("RAILWAY_PROJECT_ID", "3bf31602")
    with pytest.raises(ValidationError) as caught:
        Settings(_env_file=None, ENVIRONMENT="development", SECRET_KEY=DEFAULT_SECRET_KEY)
    assert "RAILWAY_PROJECT_ID" in str(caught.value)
    assert Settings(_env_file=None, ENVIRONMENT="development", SECRET_KEY=REAL).SECRET_KEY == REAL


def test_no_tracked_config_ships_the_literal():
    root = pathlib.Path(__file__).parent
    compose = root / "infrastructure" / "docker" / "docker-compose.yml"
    text = compose.read_text(encoding="utf-8")
    assert DEFAULT_SECRET_KEY not in text
    assert "${SECRET_KEY:?" in text
    assert "SECRET_KEY=" in (root / "infrastructure" / "docker" / ".env.example").read_text()
    assert DEFAULT_SECRET_KEY not in (root / "apps" / "api" / ".env.example").read_text()


def test_the_secondary_tree_refuses_its_own_default_when_deployed():
    from apps.api.app.core import config as secondary

    assert "Refusing" in secondary.secret_key_refusal("production", secondary.DEFAULT_SECRET_KEY)
    assert secondary.secret_key_refusal("development", secondary.DEFAULT_SECRET_KEY) == ""
    assert secondary.secret_key_refusal("production", REAL) == ""

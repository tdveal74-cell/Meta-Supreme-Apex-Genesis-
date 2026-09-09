"""Environment driven settings for the presence service.

A plain dataclass read from the process environment. pydantic-settings is
not used here on purpose: the service ships in its own image with only
``apps/presence`` and ``services`` copied in (see
``infrastructure/docker/Dockerfile.presence``), so nothing under ``app/``
can be imported, and a second BaseSettings with its own .env loading
would be a second place for the two services to disagree about a key.

What it refuses
---------------
- A deployed process (ENVIRONMENT outside development/dev/test/local, or
  a hosting platform's own marker present) is refused an empty SECRET_KEY
  and the public default. The rule and the wording are copied from
  ``app/core/config.py`` ``secret_key_refusal`` rather than imported, for
  the image reason above. If that function changes, this copy must too.
- An inference or speech name outside the known set, a fallback that
  names the same provider as the primary, a threshold that is not a
  positive integer, a partial LIVEKIT_* triple, and a CORS value that is
  not a JSON list of strings are all refused at startup, by name, rather
  than read as "mock", 0, or "not configured".

SECRET_KEY is the DEVON API's own signing key. This service never mints a
DEVON token; it only verifies the one the web client already holds, with
the same HS256 secret and the same ``type == "access"`` rule.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Mapping, Optional, Tuple

DEFAULT_SECRET_KEY = "change-me-in-production-use-openssl-rand-hex-32"

#: Environments a developer runs on their own machine. Anything else is a
#: deployment, staging included: it is reachable and it verifies real JWTs.
LOCAL_ENVIRONMENTS = frozenset({"development", "dev", "test", "local", ""})

#: Variables a hosting platform injects into every deployment it runs.
PLATFORM_MARKERS = ("RAILWAY_ENVIRONMENT_NAME", "RAILWAY_PROJECT_ID", "VERCEL_ENV")

INFERENCE_CHOICES = ("mock", "cerebras", "anthropic", "openai")
SPEECH_CHOICES = ("mock", "cartesia")

#: The voice is a compliance item in this estate rather than a default anyone
#: may fill in. Tee's standing rule is that identity is owned and never rented:
#: his own cloned voice, or a character he and his wife voice under recorded
#: consent. So a Cartesia lane with no voice named is refused at startup, and
#: no stock voice id is ever written into this repository as a fallback.
CARTESIA_VOICE_RULE = (
    "PRESENCE_SPEECH is cartesia but CARTESIA_VOICE_ID is empty. This estate's "
    "standing rule is that the voice is owned and never rented, so there is no "
    "default here and there will not be one: set CARTESIA_VOICE_ID to Tee's own "
    "cloned voice, or to a character voiced under recorded consent."
)
DEFAULT_CORS_ORIGINS: Tuple[str, ...] = ("http://localhost:3000", "http://127.0.0.1:3000")
LIVEKIT_VARIABLES = ("LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET")


class PresenceConfigError(ValueError):
    """The environment cannot be turned into a runnable configuration."""


def deployment_reason(environment: str, environ: Optional[Mapping[str, str]] = None) -> str:
    """Why this process counts as deployed, or an empty string when it is local."""
    env = (environment or "").strip().lower()
    if env not in LOCAL_ENVIRONMENTS:
        return f"ENVIRONMENT is {env}"
    variables = os.environ if environ is None else environ
    for marker in PLATFORM_MARKERS:
        if (variables.get(marker) or "").strip():
            return f"{marker} is set, so this process runs on a hosting platform"
    return ""


def secret_key_refusal(
    environment: str, secret_key: str, environ: Optional[Mapping[str, str]] = None
) -> str:
    """Why this process must not start, or an empty string when it may.

    Copied from ``app.core.config.secret_key_refusal``; see the module
    docstring for why it is a copy and not an import.
    """
    deployed = deployment_reason(environment, environ)
    if not deployed:
        return ""
    key = (secret_key or "").strip()
    if not key:
        return (
            f"SECRET_KEY is empty and {deployed}. Refusing to start: every JWT "
            "would verify against nothing. Set SECRET_KEY to the output of "
            "`openssl rand -hex 32`."
        )
    if key == DEFAULT_SECRET_KEY:
        return (
            f"SECRET_KEY is the public default and {deployed}. Refusing to start: "
            "anyone holding the repository could mint a token for any user. Set "
            "SECRET_KEY to the output of `openssl rand -hex 32`."
        )
    return ""


def _read_positive_int(environ: Mapping[str, str], name: str, default: int) -> int:
    raw = (environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise PresenceConfigError(
            f"{name} must be a whole number of milliseconds, got {raw!r}."
        ) from None
    if value <= 0:
        raise PresenceConfigError(f"{name} must be greater than zero, got {value}.")
    return value


def _read_cors_origins(environ: Mapping[str, str]) -> Tuple[str, ...]:
    raw = (environ.get("PRESENCE_CORS_ORIGINS") or "").strip()
    if not raw:
        return DEFAULT_CORS_ORIGINS
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PresenceConfigError(
            "PRESENCE_CORS_ORIGINS must be a JSON list of origin strings, for example "
            '["http://localhost:3000"]. It did not parse as JSON: ' + str(exc)
        ) from exc
    if not isinstance(parsed, list) or not all(
        isinstance(origin, str) and origin.strip() for origin in parsed
    ):
        raise PresenceConfigError(
            "PRESENCE_CORS_ORIGINS must be a JSON list of non empty origin strings, "
            f"got {raw!r}."
        )
    return tuple(origin.strip() for origin in parsed)


@dataclass(frozen=True)
class PresenceSettings:
    """Every knob the service reads, with the documented defaults."""

    SECRET_KEY: str = DEFAULT_SECRET_KEY
    JWT_ALGORITHM: str = "HS256"
    ENVIRONMENT: str = "development"
    PRESENCE_INFERENCE: str = "mock"
    PRESENCE_FALLBACK_INFERENCE: str = ""
    CEREBRAS_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    PRESENCE_SPEECH: str = "mock"
    CARTESIA_API_KEY: str = ""
    CARTESIA_VOICE_ID: str = ""
    CARTESIA_MODEL: str = "sonic-3"
    CARTESIA_LANGUAGE: str = "en"
    LIVEKIT_URL: str = ""
    LIVEKIT_API_KEY: str = ""
    LIVEKIT_API_SECRET: str = ""
    PRESENCE_TTFT_THRESHOLD_MS: int = 500
    PRESENCE_WINDOW_MS: int = 250
    PRESENCE_CORS_ORIGINS: Tuple[str, ...] = DEFAULT_CORS_ORIGINS

    @property
    def livekit_configured(self) -> bool:
        return all(
            (getattr(self, name) or "").strip() for name in LIVEKIT_VARIABLES
        )

    def validate(self, environ: Optional[Mapping[str, str]] = None) -> "PresenceSettings":
        """Raise PresenceConfigError naming the first thing that is wrong."""
        refusal = secret_key_refusal(self.ENVIRONMENT, self.SECRET_KEY, environ)
        if refusal:
            raise PresenceConfigError(refusal)

        if self.PRESENCE_INFERENCE not in INFERENCE_CHOICES:
            raise PresenceConfigError(
                f"PRESENCE_INFERENCE is {self.PRESENCE_INFERENCE!r}; it must be one of "
                f"{', '.join(INFERENCE_CHOICES)}."
            )
        if self.PRESENCE_FALLBACK_INFERENCE and (
            self.PRESENCE_FALLBACK_INFERENCE not in INFERENCE_CHOICES
        ):
            raise PresenceConfigError(
                f"PRESENCE_FALLBACK_INFERENCE is {self.PRESENCE_FALLBACK_INFERENCE!r}; "
                f"it must be empty or one of {', '.join(INFERENCE_CHOICES)}."
            )
        if self.PRESENCE_FALLBACK_INFERENCE == self.PRESENCE_INFERENCE:
            raise PresenceConfigError(
                f"PRESENCE_FALLBACK_INFERENCE names the primary ({self.PRESENCE_INFERENCE}). "
                "A fallback on the same provider fails the same way; leave it empty or "
                "name a different one."
            )
        if self.PRESENCE_SPEECH not in SPEECH_CHOICES:
            raise PresenceConfigError(
                f"PRESENCE_SPEECH is {self.PRESENCE_SPEECH!r}; it must be one of "
                f"{', '.join(SPEECH_CHOICES)}."
            )
        if self.PRESENCE_SPEECH == "cartesia":
            # Refused here as well as in build_speech, because these two answer
            # different questions. build_speech refuses to hand back a
            # synthesiser that cannot speak; this refuses to call the
            # configuration valid at all, which is what the settings tests and
            # any future caller of validate() read.
            if not self.CARTESIA_API_KEY:
                raise PresenceConfigError(
                    "PRESENCE_SPEECH is cartesia but CARTESIA_API_KEY is empty. Set the "
                    "key or switch PRESENCE_SPEECH to mock."
                )
            if not self.CARTESIA_VOICE_ID:
                raise PresenceConfigError(CARTESIA_VOICE_RULE)
        if self.PRESENCE_TTFT_THRESHOLD_MS <= 0:
            raise PresenceConfigError("PRESENCE_TTFT_THRESHOLD_MS must be greater than zero.")
        if self.PRESENCE_WINDOW_MS <= 0:
            raise PresenceConfigError("PRESENCE_WINDOW_MS must be greater than zero.")

        present = [name for name in LIVEKIT_VARIABLES if (getattr(self, name) or "").strip()]
        if present and len(present) != len(LIVEKIT_VARIABLES):
            missing = [name for name in LIVEKIT_VARIABLES if name not in present]
            raise PresenceConfigError(
                f"LiveKit is half configured: {', '.join(present)} set but "
                f"{', '.join(missing)} empty. Set all three or none."
            )
        if self.JWT_ALGORITHM != "HS256":
            raise PresenceConfigError(
                f"JWT_ALGORITHM is {self.JWT_ALGORITHM!r}. The DEVON API signs with HS256 "
                "and this service verifies with the same shared secret; another "
                "algorithm here would verify nothing the API mints."
            )
        return self

    @classmethod
    def from_env(cls, environ: Optional[Mapping[str, str]] = None) -> "PresenceSettings":
        """Read and validate. Raises PresenceConfigError rather than starting wrong."""
        variables = os.environ if environ is None else environ

        def text(name: str, default: str = "") -> str:
            value = variables.get(name)
            return default if value is None else value.strip()

        settings = cls(
            SECRET_KEY=text("SECRET_KEY", DEFAULT_SECRET_KEY),
            JWT_ALGORITHM=text("JWT_ALGORITHM", "HS256") or "HS256",
            ENVIRONMENT=text("ENVIRONMENT", "development"),
            PRESENCE_INFERENCE=text("PRESENCE_INFERENCE", "mock").lower() or "mock",
            PRESENCE_FALLBACK_INFERENCE=text("PRESENCE_FALLBACK_INFERENCE").lower(),
            CEREBRAS_API_KEY=text("CEREBRAS_API_KEY"),
            ANTHROPIC_API_KEY=text("ANTHROPIC_API_KEY"),
            OPENAI_API_KEY=text("OPENAI_API_KEY"),
            PRESENCE_SPEECH=text("PRESENCE_SPEECH", "mock").lower() or "mock",
            CARTESIA_API_KEY=text("CARTESIA_API_KEY"),
            CARTESIA_VOICE_ID=text("CARTESIA_VOICE_ID"),
            CARTESIA_MODEL=text("CARTESIA_MODEL", "sonic-3") or "sonic-3",
            CARTESIA_LANGUAGE=text("CARTESIA_LANGUAGE", "en") or "en",
            LIVEKIT_URL=text("LIVEKIT_URL"),
            LIVEKIT_API_KEY=text("LIVEKIT_API_KEY"),
            LIVEKIT_API_SECRET=text("LIVEKIT_API_SECRET"),
            PRESENCE_TTFT_THRESHOLD_MS=_read_positive_int(
                variables, "PRESENCE_TTFT_THRESHOLD_MS", 500
            ),
            PRESENCE_WINDOW_MS=_read_positive_int(variables, "PRESENCE_WINDOW_MS", 250),
            PRESENCE_CORS_ORIGINS=_read_cors_origins(variables),
        )
        return settings.validate(variables)

"""
Provider factory — configuration in, provider out.

The application layer (FastAPI) passes plain values from its settings; the
services layer never imports application config, keeping the dependency
direction app → services.
"""

from __future__ import annotations

from typing import Optional

from services.intelligence.providers.anthropic_provider import AnthropicProvider
from services.intelligence.providers.base import AIProvider, ProviderConfigError
from services.intelligence.providers.cerebras_provider import (
    DEFAULT_MODEL as CEREBRAS_DEFAULT_MODEL,
)
from services.intelligence.providers.cerebras_provider import CerebrasProvider
from services.intelligence.providers.mock_provider import MockProvider
from services.intelligence.providers.openai_provider import OpenAIProvider

SUPPORTED_PROVIDERS = ("mock", "anthropic", "openai", "cerebras")


def create_provider(
    provider_name: str,
    *,
    anthropic_api_key: Optional[str] = None,
    openai_api_key: Optional[str] = None,
    cerebras_api_key: Optional[str] = None,
    model: Optional[str] = None,
    timeout_seconds: float = 60.0,
    max_retries: int = 2,
) -> AIProvider:
    """
    Build the configured AI provider.

    Raises ProviderConfigError for unknown providers or missing credentials —
    misconfiguration must fail loudly, never silently degrade.
    """
    name = (provider_name or "").strip().lower()

    if name == "mock":
        return MockProvider(
            default_model=model or "mock-council-v1",
            max_retries=0,
        )

    if name == "anthropic":
        return AnthropicProvider(
            api_key=anthropic_api_key or "",
            default_model=model or "claude-sonnet-5",
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )

    if name == "openai":
        return OpenAIProvider(
            api_key=openai_api_key or "",
            default_model=model or "gpt-5.2",
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )

    if name == "cerebras":
        # Timeout is deliberately tighter than the others. The measured latency
        # on this lane is 42ms, so a 60s wait would mask a dead endpoint for a
        # minute on a call that normally answers instantly.
        return CerebrasProvider(
            api_key=cerebras_api_key or "",
            default_model=model or CEREBRAS_DEFAULT_MODEL,
            timeout_seconds=min(timeout_seconds, 30.0),
            max_retries=max_retries,
        )

    raise ProviderConfigError(
        f"Unknown AI provider '{provider_name}'. "
        f"Supported providers: {', '.join(SUPPORTED_PROVIDERS)}."
    )


def create_completion_provider(
    provider_name: str,
    *,
    anthropic_api_key: Optional[str] = None,
    openai_api_key: Optional[str] = None,
    cerebras_api_key: Optional[str] = None,
    model: Optional[str] = None,
    timeout_seconds: float = 60.0,
    max_retries: int = 2,
) -> AIProvider:
    """Build the configured completion provider: name in, provider out.

    The completion-side counterpart to `create_embedding_provider` below,
    kept under the name callers of a cross-encoder judge or any other
    completion-only lane actually look for. There is nothing provider-
    specific left to write here: `create_provider` already builds and tests
    every one of these providers for the Council, so this delegates to it
    rather than re-implementing the same per-provider construction (and
    its own chance of drifting out of sync) a second time.
    """
    return create_provider(
        provider_name,
        anthropic_api_key=anthropic_api_key,
        openai_api_key=openai_api_key,
        cerebras_api_key=cerebras_api_key,
        model=model,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
    )

"""
AI provider abstraction.

These modules were flattened to the repository root by a zip restore, but they
never stopped importing each other as `services.intelligence.providers.*` — the
package they were written in. Restoring the package is what makes those imports
resolve; nothing inside the modules had to change.
"""

from services.intelligence.providers.base import (
    AIProvider,
    ChatMessage,
    CompletionRequest,
    CompletionResponse,
    ProviderAuthError,
    ProviderConfigError,
    ProviderError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderServerError,
    ProviderTimeoutError,
    TokenUsage,
    extract_json,
)
from services.intelligence.providers.anthropic_provider import AnthropicProvider
from services.intelligence.providers.embeddings import (
    EmbeddingProvider,
    EmbeddingResponse,
    MockEmbeddingProvider,
    OpenAIEmbeddingProvider,
    create_embedding_provider,
)
from services.intelligence.providers.factory import create_provider
from services.intelligence.providers.mock_provider import MockProvider
from services.intelligence.providers.openai_provider import OpenAIProvider

__all__ = [
    "AIProvider",
    "AnthropicProvider",
    "ChatMessage",
    "EmbeddingProvider",
    "EmbeddingResponse",
    "MockEmbeddingProvider",
    "OpenAIEmbeddingProvider",
    "create_embedding_provider",
    "CompletionRequest",
    "CompletionResponse",
    "MockProvider",
    "OpenAIProvider",
    "ProviderAuthError",
    "ProviderConfigError",
    "ProviderError",
    "ProviderRateLimitError",
    "ProviderResponseError",
    "ProviderServerError",
    "ProviderTimeoutError",
    "TokenUsage",
    "create_provider",
    "extract_json",
]

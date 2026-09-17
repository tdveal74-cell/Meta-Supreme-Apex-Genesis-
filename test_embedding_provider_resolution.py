"""Embeddings read EMBEDDING_PROVIDER, and never the chat provider.

WHAT THIS FILE IS DEFENDING, AND WHY IT IS WORTH A FILE

Until 2026-09-17 both embedding resolvers in this repo looked for a settings
field called `DEFAULT_EMBEDDING_PROVIDER`, did not find it because it does not
exist, and fell through to `DEFAULT_AI_PROVIDER`. That welded embeddings to the
CHAT provider.

On this estate chat runs on Cerebras, which has no embeddings endpoint, so the
weld did not degrade retrieval, it broke it: every embedding call resolved to
'cerebras' and raised ProviderConfigError. Meanwhile `EMBEDDING_PROVIDER` sat
on the production api service, documented in `app/core/config.py` as the switch
for real semantic retrieval, read by nothing.

The reason it needs pinning rather than just fixing is that the fallback looks
helpful. A future reader who finds `resolve_embedding_provider_name` returning
"mock" while `DEFAULT_AI_PROVIDER=openai` will be tempted to add the fallback
back so embeddings "just follow the chat provider". That is the bug. These
tests fail if they do.
"""

from __future__ import annotations

import logging

import pytest

from services.intelligence.providers.embeddings import (
    SUPPORTED_EMBEDDING_PROVIDERS,
    resolve_embedding_provider_name,
)


class _Settings:
    """Only the fields the resolver is allowed to read."""

    def __init__(self, **fields: object) -> None:
        for key, value in fields.items():
            setattr(self, key, value)


def test_embedding_provider_is_the_control() -> None:
    """The field that names itself is the one that decides."""
    settings = _Settings(EMBEDDING_PROVIDER="openai", DEFAULT_AI_PROVIDER="cerebras")
    assert resolve_embedding_provider_name(settings) == "openai"


def test_the_production_shape_no_longer_resolves_to_a_chat_provider() -> None:
    """The exact configuration that was live and broken.

    EMBEDDING_PROVIDER=openai, chat on cerebras. Before the fix this returned
    'cerebras' and `create_embedding_provider` raised ProviderConfigError, so
    every semantic search on the deployed api failed.
    """
    settings = _Settings(EMBEDDING_PROVIDER="openai", DEFAULT_AI_PROVIDER="cerebras")
    resolved = resolve_embedding_provider_name(settings)
    assert resolved != "cerebras"
    assert resolved in SUPPORTED_EMBEDDING_PROVIDERS


def test_the_chat_provider_is_never_a_fallback() -> None:
    """The anti weld test, and the reason this file exists.

    With embeddings unset and chat on a provider that CAN embed, the tempting
    behaviour is to follow the chat provider. Doing that is what tied the two
    together in the first place, so it must not happen even when it would
    "work".
    """
    settings = _Settings(DEFAULT_AI_PROVIDER="openai")
    assert resolve_embedding_provider_name(settings) == "mock"

    # And the case that motivated the whole thing: a chat provider that cannot
    # embed must not reach the factory at all.
    settings = _Settings(DEFAULT_AI_PROVIDER="cerebras")
    assert resolve_embedding_provider_name(settings) == "mock"


def test_the_silent_downgrade_is_not_silent(caplog: pytest.LogCaptureFixture) -> None:
    """Falling to mock while the chat provider could embed must be audible.

    This is the one case where the fix costs a deployment something: anyone who
    got real embeddings by setting only DEFAULT_AI_PROVIDER=openai now gets
    mock. Mock vectors are deterministic and plausible, and under them a
    sourdough recipe scored 0.6406 against the jobs episode while an on topic
    question scored 0.6170, so a quiet downgrade would rank nonsense as recall.
    """
    settings = _Settings(DEFAULT_AI_PROVIDER="openai")
    with caplog.at_level(logging.WARNING):
        assert resolve_embedding_provider_name(settings) == "mock"
    assert any("EMBEDDING_PROVIDER" in r.getMessage() for r in caplog.records), (
        "a downgrade from real vectors to mock has to name the variable that fixes it"
    )


def test_a_chat_provider_that_cannot_embed_does_not_warn(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """No warning when nothing was lost.

    Cerebras cannot embed, so mock is not a downgrade from it. Warning here
    would train the reader to ignore the warning that matters.
    """
    settings = _Settings(DEFAULT_AI_PROVIDER="cerebras")
    with caplog.at_level(logging.WARNING):
        resolve_embedding_provider_name(settings)
    assert not caplog.records


def test_missing_and_junk_values_land_on_mock() -> None:
    """The safe end, and never an exception on a read."""
    assert resolve_embedding_provider_name(_Settings()) == "mock"
    assert resolve_embedding_provider_name(_Settings(EMBEDDING_PROVIDER="")) == "mock"
    assert resolve_embedding_provider_name(_Settings(EMBEDDING_PROVIDER="   ")) == "mock"
    assert resolve_embedding_provider_name(_Settings(EMBEDDING_PROVIDER=None)) == "mock"
    assert resolve_embedding_provider_name(_Settings(EMBEDDING_PROVIDER=42)) == "mock"
    assert resolve_embedding_provider_name(_Settings(EMBEDDING_PROVIDER=" OpenAI ")) == "openai"


def test_the_field_the_old_code_looked_for_still_does_not_exist() -> None:
    """The reason the weld was invisible, pinned.

    Both resolvers read `DEFAULT_EMBEDDING_PROVIDER` and fell through when it
    was absent. It was always absent. If someone later ADDS that field, this
    test fails and they are made to decide deliberately rather than resurrect
    the fallback by accident.
    """
    from app.core.config import settings

    assert not hasattr(settings, "DEFAULT_EMBEDDING_PROVIDER")
    assert hasattr(settings, "EMBEDDING_PROVIDER")


def _settings_fields_read(function) -> set:
    """Every settings field name the function's CODE reads.

    Read from the AST rather than by substring, because both resolvers carry
    docstrings that name `DEFAULT_AI_PROVIDER` while explaining the bug this
    file exists for. A substring check would fail on the explanation and pass
    on a comment that said nothing, which is the wrong way round.
    """
    import ast
    import inspect
    import textwrap

    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    names = set()
    for node in ast.walk(tree):
        # settings.FIELD
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id == "settings":
                names.add(node.attr)
        # getattr(settings, "FIELD", ...)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == "getattr" and len(node.args) >= 2:
                target, field = node.args[0], node.args[1]
                if isinstance(target, ast.Name) and target.id == "settings":
                    if isinstance(field, ast.Constant) and isinstance(field.value, str):
                        names.add(field.value)
    return names


def test_both_lanes_resolve_through_the_shared_function() -> None:
    """Two resolvers drifted into the same bug once. They share one now."""
    import inspect

    from app.services import knowledge
    from services.knowledge import pipeline

    for module in (knowledge, pipeline):
        source = inspect.getsource(module._embedding_provider)
        assert "resolve_embedding_provider_name" in source, (
            f"{module.__name__} resolves the embedding provider on its own again"
        )
        read = _settings_fields_read(module._embedding_provider)
        assert "DEFAULT_AI_PROVIDER" not in read, (
            f"{module.__name__} reads the chat provider for embeddings again; "
            f"it reads {sorted(read)}"
        )
        assert "DEFAULT_EMBEDDING_PROVIDER" not in read, (
            f"{module.__name__} looks for the field that never existed again"
        )

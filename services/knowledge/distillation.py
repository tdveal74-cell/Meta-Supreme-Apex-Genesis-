"""Contextual distillation before embedding.

Produces searchable structured text from raw content. Failures are explicit.
Mock path is labelled and deterministic so tests stay offline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class DistilledDocument:
    searchable_text: str
    summary: str
    key_facts: list[str]
    systems_refs: list[str]
    simulated: bool = False


_WS = re.compile(r"\s+")


def _first_sentences(text: str, n: int = 2) -> str:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(p.strip() for p in parts[:n] if p.strip())


def _bullet_facts(text: str, limit: int = 5) -> list[str]:
    lines = [ln.strip(" -*\t") for ln in text.splitlines() if ln.strip()]
    facts: list[str] = []
    for ln in lines:
        if len(ln) < 20:
            continue
        facts.append(ln[:240])
        if len(facts) >= limit:
            break
    if not facts:
        summary = _first_sentences(text, 3)
        if summary:
            facts = [summary]
    return facts


def _systems_refs(text: str) -> list[str]:
    patterns = [
        r"\b(Meta Supreme|EditForge|Devon|n8n|Tagga|Psycle|Airtable|GitHub|Notion)\b",
        r"\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b",
    ]
    found: list[str] = []
    seen: set[str] = set()
    for pat in patterns:
        for m in re.finditer(pat, text):
            token = m.group(0)
            if token.lower() in seen:
                continue
            seen.add(token.lower())
            found.append(token)
            if len(found) >= 12:
                return found
    return found


def distill_content(
    *,
    title: str,
    content: str,
    source: Optional[str] = None,
    use_llm: bool = False,
) -> DistilledDocument:
    """
    Distill raw content into searchable text.

    use_llm=False is the default offline path (deterministic, labelled simulated
    when no live LLM is wired).
    """
    title = (title or "Untitled").strip()
    content = (content or "").strip()
    if not content:
        raise ValueError("distillation requires non-empty content")

    summary = _first_sentences(content, 2)
    facts = _bullet_facts(content)
    refs = _systems_refs(content)
    source_line = f"Source: {source}" if source else ""

    blocks = [
        f"Title: {title}",
        source_line,
        f"Summary: {summary}" if summary else "",
        "Key facts:",
        *[f"- {f}" for f in facts],
        "Systems and code refs:" if refs else "",
        *[f"- {r}" for r in refs],
        "Body:",
        content[:8000],
    ]
    searchable = "\n".join(b for b in blocks if b)
    searchable = _WS.sub(" ", searchable.replace("\n", " \n ")).strip()

    return DistilledDocument(
        searchable_text=searchable,
        summary=summary or title,
        key_facts=facts,
        systems_refs=refs,
        simulated=not use_llm,
    )

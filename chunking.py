"""
Text chunking for the knowledge pipeline.

Paragraph-aware splitting with overlap: chunks break on paragraph
boundaries where possible, fall back to sentence/word boundaries for very
long paragraphs, and carry a configurable overlap so retrieval never loses
context at chunk edges. Pure functions — no framework, no I/O.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

DEFAULT_CHUNK_CHARS = 1500
DEFAULT_OVERLAP_CHARS = 200

_PARAGRAPH_RE = re.compile(r"\n\s*\n")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass
class Chunk:
    index: int
    content: str


def _split_long_text(text: str, limit: int) -> List[str]:
    """Split an over-long paragraph on sentences, then words, never mid-word."""
    if len(text) <= limit:
        return [text]

    pieces: List[str] = []
    current = ""
    for sentence in _SENTENCE_RE.split(text):
        if not sentence:
            continue
        if len(sentence) > limit:
            # Pathologically long sentence: split on words.
            words = sentence.split(" ")
            for word in words:
                if len(current) + len(word) + 1 > limit and current:
                    pieces.append(current.strip())
                    current = ""
                current += word + " "
            continue
        if len(current) + len(sentence) + 1 > limit and current:
            pieces.append(current.strip())
            current = ""
        current += sentence + " "
    if current.strip():
        pieces.append(current.strip())
    return pieces


def chunk_text(
    text: str,
    *,
    chunk_chars: int = DEFAULT_CHUNK_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
) -> List[Chunk]:
    """
    Split text into ordered, overlapping chunks.

    Empty/whitespace-only input yields no chunks. Overlap is taken from the
    tail of the previous chunk so each chunk stands alone in retrieval.
    """
    normalized = text.replace("\r\n", "\n").strip()
    if not normalized:
        return []

    # Build paragraph-sized units, splitting any that exceed the limit.
    units: List[str] = []
    for paragraph in _PARAGRAPH_RE.split(normalized):
        paragraph = paragraph.strip()
        if paragraph:
            units.extend(_split_long_text(paragraph, chunk_chars))

    chunks: List[str] = []
    current = ""
    for unit in units:
        candidate = f"{current}\n\n{unit}" if current else unit
        if len(candidate) > chunk_chars and current:
            chunks.append(current)
            tail = current[-overlap_chars:] if overlap_chars > 0 else ""
            current = f"{tail}\n\n{unit}".strip() if tail else unit
            # If even the fresh unit overflows (rare), hard-append it.
            if len(current) > chunk_chars:
                chunks.append(current[:chunk_chars])
                current = current[chunk_chars - overlap_chars :] if overlap_chars else ""
        else:
            current = candidate
    if current.strip():
        chunks.append(current.strip())

    return [Chunk(index=i, content=c) for i, c in enumerate(chunks)]

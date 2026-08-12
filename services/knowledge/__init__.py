"""
Knowledge services — chunking, and the embedding surface it feeds.

`chunk_text` is re-exported here because that is the name the suite and the
knowledge API both import; the module underneath was flattened to the repo root
by a zip restore and is back where its callers always looked for it.
"""

from services.knowledge.chunking import Chunk, chunk_text

__all__ = ["Chunk", "chunk_text"]

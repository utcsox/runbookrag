"""Embed chunks produced by app.ingestion.chunking for storage in pgvector.

Uses a local sentence-transformers model so embedding generation has no
external API dependency, API key, or per-call cost.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache

from sentence_transformers import SentenceTransformer

from app.ingestion.chunking import Chunk

DEFAULT_MODEL_NAME = "all-MiniLM-L6-v2"


@dataclass
class EmbeddedChunk:
    chunk: Chunk
    embedding: list[float]
    model: str


@cache
def _load_model(model_name: str) -> SentenceTransformer:
    return SentenceTransformer(model_name)


def embedding_dimension(model_name: str = DEFAULT_MODEL_NAME) -> int:
    return _load_model(model_name).get_embedding_dimension()


def embed_chunks(
    chunks: list[Chunk],
    model_name: str = DEFAULT_MODEL_NAME,
    batch_size: int = 32,
) -> list[EmbeddedChunk]:
    if not chunks:
        return []

    model = _load_model(model_name)
    vectors = model.encode(
        [chunk.text for chunk in chunks],
        batch_size=batch_size,
        show_progress_bar=False,
    )
    return [
        EmbeddedChunk(chunk=chunk, embedding=vector.tolist(), model=model_name)
        for chunk, vector in zip(chunks, vectors, strict=True)
    ]

"""Retrieve the most relevant stored chunks for a natural-language query.

Thin layer over app.ingestion.embedder and app.ingestion.store: embeds
the query with the same model used at ingestion time, then runs a
cosine-distance nearest-neighbor search in pgvector.
"""

from __future__ import annotations

from dataclasses import dataclass

import psycopg

from app.ingestion.embedder import DEFAULT_MODEL_NAME, embed_text
from app.ingestion.store import query_similar


@dataclass
class RetrievedChunk:
    text: str
    heading_path: list[str]
    source: str
    chunk_index: int
    distance: float


def retrieve(
    conn: psycopg.Connection,
    query: str,
    k: int = 5,
    source: str | None = None,
    model_name: str = DEFAULT_MODEL_NAME,
) -> list[RetrievedChunk]:
    query_embedding = embed_text(query, model_name=model_name)
    rows = query_similar(conn, query_embedding, k=k, source=source)
    return [
        RetrievedChunk(
            text=text,
            heading_path=heading_path,
            source=row_source,
            chunk_index=chunk_index,
            distance=distance,
        )
        for _id, row_source, chunk_index, heading_path, text, model, distance in rows
    ]

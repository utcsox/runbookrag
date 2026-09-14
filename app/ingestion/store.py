"""Store embedded chunks in the pgvector-backed Postgres database.

Uses psycopg (v3) directly rather than an ORM, matching the rest of the
ingestion pipeline. Re-ingesting the same chunk (same source + chunk_index)
overwrites rather than duplicates it, via a deterministic id.
"""

from __future__ import annotations

import hashlib
import os

import psycopg
from pgvector import Vector
from pgvector.psycopg import register_vector

from app.ingestion.embedder import (
    DEFAULT_MODEL_NAME,
    EmbeddedChunk,
    embedding_dimension,
)

DEFAULT_DATABASE_URL = "postgresql://runbookrag:runbookrag@localhost:5432/runbookrag"


def connect() -> psycopg.Connection:
    url = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    try:
        conn = psycopg.connect(url, autocommit=True)
    except psycopg.OperationalError as e:
        raise psycopg.OperationalError(
            "Could not connect to Postgres. Is the database running? "
            "Start it with: docker compose up -d db"
        ) from e
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    register_vector(conn)
    return conn


def ensure_schema(conn: psycopg.Connection, model_name: str = DEFAULT_MODEL_NAME) -> None:
    dim = embedding_dimension(model_name)
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS chunks (
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            heading_path TEXT[] NOT NULL,
            text TEXT NOT NULL,
            model TEXT NOT NULL,
            embedding VECTOR({dim}) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )


def _chunk_id(embedded: EmbeddedChunk) -> str:
    raw = f"{embedded.chunk.source}:{embedded.chunk.chunk_index}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def store_chunks(conn: psycopg.Connection, embedded_chunks: list[EmbeddedChunk]) -> None:
    if not embedded_chunks:
        return

    rows = [
        (
            _chunk_id(item),
            item.chunk.source,
            item.chunk.chunk_index,
            item.chunk.heading_path,
            item.chunk.text,
            item.model,
            item.embedding,
        )
        for item in embedded_chunks
    ]
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO chunks (id, source, chunk_index, heading_path, text, model, embedding)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                source = EXCLUDED.source,
                chunk_index = EXCLUDED.chunk_index,
                heading_path = EXCLUDED.heading_path,
                text = EXCLUDED.text,
                model = EXCLUDED.model,
                embedding = EXCLUDED.embedding,
                created_at = now()
            """,
            rows,
        )


def delete_by_source(conn: psycopg.Connection, source: str) -> None:
    conn.execute("DELETE FROM chunks WHERE source = %s", (source,))


def count(conn: psycopg.Connection) -> int:
    return conn.execute("SELECT count(*) FROM chunks").fetchone()[0]


def count_by_source(conn: psycopg.Connection, source: str) -> int:
    return conn.execute(
        "SELECT count(*) FROM chunks WHERE source = %s", (source,)
    ).fetchone()[0]


def query_similar(
    conn: psycopg.Connection,
    embedding: list[float],
    k: int = 5,
    source: str | None = None,
):
    query_vector = Vector(embedding)
    where_clause = "WHERE source = %s" if source is not None else ""
    params = (
        (query_vector, source, query_vector, k)
        if source is not None
        else (query_vector, query_vector, k)
    )
    return conn.execute(
        f"""
        SELECT id, source, chunk_index, heading_path, text, model,
               embedding <=> %s AS distance
        FROM chunks
        {where_clause}
        ORDER BY embedding <=> %s
        LIMIT %s
        """,
        params,
    ).fetchall()

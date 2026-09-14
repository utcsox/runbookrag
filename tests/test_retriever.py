import pytest

from app.ingestion.chunking import Chunk
from app.ingestion.embedder import embed_chunks
from app.ingestion.store import connect, delete_by_source, ensure_schema, store_chunks
from app.retrieval.retriever import retrieve

TEST_SOURCE = "test-retriever.md"


@pytest.fixture
def conn():
    connection = connect()
    ensure_schema(connection)
    delete_by_source(connection, TEST_SOURCE)

    chunks = [
        Chunk(
            text="Redis is down and not responding to PING",
            heading_path=["Redis", "Troubleshooting"],
            source=TEST_SOURCE,
            chunk_index=0,
        ),
        Chunk(
            text="Gitaly repository storage is corrupted",
            heading_path=["Gitaly", "Troubleshooting"],
            source=TEST_SOURCE,
            chunk_index=1,
        ),
        Chunk(
            text="Bake sourdough bread with a long cold proof",
            heading_path=["Recipes"],
            source=TEST_SOURCE,
            chunk_index=2,
        ),
    ]
    store_chunks(connection, embed_chunks(chunks))

    yield connection

    delete_by_source(connection, TEST_SOURCE)
    connection.close()


def test_retrieve_returns_most_relevant_first(conn):
    results = retrieve(conn, "redis server unreachable", k=3, source=TEST_SOURCE)

    assert results[0].text == "Redis is down and not responding to PING"
    assert results[0].heading_path == ["Redis", "Troubleshooting"]
    assert results[0].chunk_index == 0
    assert results[0].distance < results[1].distance < results[2].distance


def test_retrieve_respects_k(conn):
    results = retrieve(conn, "redis server unreachable", k=1, source=TEST_SOURCE)
    assert len(results) == 1


def test_retrieve_scopes_to_source(conn):
    results = retrieve(conn, "redis server unreachable", k=10, source="nonexistent.md")
    assert results == []


def test_retrieve_unrelated_query_ranks_bread_last(conn):
    results = retrieve(conn, "sourdough starter hydration", k=3, source=TEST_SOURCE)
    assert results[0].text == "Bake sourdough bread with a long cold proof"

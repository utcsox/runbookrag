import pytest

from app.ingestion.chunking import Chunk
from app.ingestion.embedder import EmbeddedChunk, embedding_dimension
from app.ingestion.store import (
    connect,
    count,
    count_by_source,
    delete_by_source,
    ensure_schema,
    query_similar,
    store_chunks,
)

TEST_SOURCE = "test-store.md"
DIM = embedding_dimension()


def _embedded(text: str, chunk_index: int, embedding: list[float]) -> EmbeddedChunk:
    chunk = Chunk(
        text=text, heading_path=["Test"], source=TEST_SOURCE, chunk_index=chunk_index
    )
    return EmbeddedChunk(chunk=chunk, embedding=embedding, model="test-model")


def _unit_vector(index: int) -> list[float]:
    vector = [0.0] * DIM
    vector[index] = 1.0
    return vector


@pytest.fixture
def conn():
    connection = connect()
    ensure_schema(connection)
    delete_by_source(connection, TEST_SOURCE)
    yield connection
    delete_by_source(connection, TEST_SOURCE)
    connection.close()


def test_store_chunks_persists_rows(conn):
    items = [
        _embedded("alpha", 0, _unit_vector(0)),
        _embedded("beta", 1, _unit_vector(1)),
    ]

    store_chunks(conn, items)

    assert count_by_source(conn, TEST_SOURCE) == 2


def test_store_chunks_upsert_does_not_duplicate(conn):
    item = _embedded("gamma", 0, _unit_vector(2))

    store_chunks(conn, [item])
    store_chunks(conn, [item])

    assert count_by_source(conn, TEST_SOURCE) == 1


def test_store_chunks_empty_list_is_a_noop(conn):
    store_chunks(conn, [])
    assert count_by_source(conn, TEST_SOURCE) == 0


def test_delete_by_source_removes_only_that_source(conn):
    other_source_item = EmbeddedChunk(
        chunk=Chunk(
            text="other", heading_path=[], source="other.md", chunk_index=0
        ),
        embedding=_unit_vector(3),
        model="test-model",
    )
    store_chunks(conn, [_embedded("mine", 0, _unit_vector(4)), other_source_item])

    delete_by_source(conn, TEST_SOURCE)

    assert count_by_source(conn, TEST_SOURCE) == 0
    assert count_by_source(conn, "other.md") == 1
    delete_by_source(conn, "other.md")


def test_query_similar_orders_by_distance(conn):
    store_chunks(
        conn,
        [
            _embedded("close", 0, _unit_vector(0)),
            _embedded("far", 1, _unit_vector(1)),
        ],
    )

    results = query_similar(conn, _unit_vector(0), k=2, source=TEST_SOURCE)

    assert [row[4] for row in results] == ["close", "far"]
    assert results[0][6] < results[1][6]


def test_query_similar_scopes_to_source(conn):
    store_chunks(conn, [_embedded("mine", 0, _unit_vector(0))])

    results = query_similar(conn, _unit_vector(0), k=10, source="nonexistent-source.md")

    assert results == []


def test_count_reflects_total_rows(conn):
    before = count(conn)
    store_chunks(conn, [_embedded("alpha", 0, _unit_vector(0))])

    assert count(conn) == before + 1

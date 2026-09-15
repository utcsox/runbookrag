import pytest
from fastapi.testclient import TestClient

from app.ingestion.chunking import Chunk
from app.ingestion.embedder import embed_chunks
from app.ingestion.store import connect, delete_by_source, ensure_schema, store_chunks
from app.main import app

client = TestClient(app)

TEST_SOURCE = "test-main-search.md"


def test_health_check():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


@pytest.fixture
def seeded_source():
    conn = connect()
    ensure_schema(conn)
    delete_by_source(conn, TEST_SOURCE)

    chunks = [
        Chunk(
            text="Redis is down and not responding to PING",
            heading_path=["Redis"],
            source=TEST_SOURCE,
            chunk_index=0,
        ),
        Chunk(
            text="Bake sourdough bread with a long cold proof",
            heading_path=["Recipes"],
            source=TEST_SOURCE,
            chunk_index=1,
        ),
    ]
    store_chunks(conn, embed_chunks(chunks))

    yield

    delete_by_source(conn, TEST_SOURCE)
    conn.close()


def test_search_returns_ranked_results_with_score(seeded_source):
    with TestClient(app) as test_client:
        response = test_client.post(
            "/search",
            json={"query": "redis server unreachable", "k": 2, "source": TEST_SOURCE},
        )

    assert response.status_code == 200
    body = response.json()
    assert len(body["results"]) == 2
    assert body["results"][0]["text"] == "Redis is down and not responding to PING"
    assert body["results"][0]["heading_path"] == ["Redis"]
    assert body["results"][0]["score"] > body["results"][1]["score"]


def test_search_rejects_empty_query():
    with TestClient(app) as test_client:
        response = test_client.post("/search", json={"query": ""})
    assert response.status_code == 422


def test_search_rejects_out_of_range_k():
    with TestClient(app) as test_client:
        response = test_client.post("/search", json={"query": "test", "k": 0})
    assert response.status_code == 422

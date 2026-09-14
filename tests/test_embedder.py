import math

from app.ingestion.chunking import Chunk
from app.ingestion.embedder import _load_model, embed_chunks


def _chunk(text: str) -> Chunk:
    return Chunk(text=text, heading_path=["Test"], source="test.md", chunk_index=0)


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    return dot / (norm_a * norm_b)


def test_embed_chunks_empty_list_returns_empty():
    assert embed_chunks([]) == []


def test_embed_chunks_returns_one_vector_per_chunk():
    chunks = [_chunk("Redis is down"), _chunk("Gitaly is down")]
    embedded = embed_chunks(chunks)

    assert len(embedded) == 2
    for item, chunk in zip(embedded, chunks, strict=True):
        assert item.chunk is chunk
        assert item.model == "all-MiniLM-L6-v2"
        assert len(item.embedding) > 0
        assert all(isinstance(x, float) for x in item.embedding)


def test_embeddings_capture_semantic_similarity():
    embedded = embed_chunks(
        [
            _chunk("Redis is down and not responding to PING"),
            _chunk("The Redis server is unreachable and failing health checks"),
            _chunk("Bake sourdough bread with a long cold proof"),
        ]
    )
    redis_a, redis_b, unrelated = (item.embedding for item in embedded)

    sim_related = _cosine(redis_a, redis_b)
    sim_unrelated = _cosine(redis_a, unrelated)

    assert sim_related > sim_unrelated


def test_model_is_cached_across_calls():
    first = _load_model("all-MiniLM-L6-v2")
    second = _load_model("all-MiniLM-L6-v2")
    assert first is second

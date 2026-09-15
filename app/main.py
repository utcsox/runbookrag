from collections.abc import Iterator
from contextlib import asynccontextmanager

import psycopg
from fastapi import Depends, FastAPI
from pydantic import BaseModel, Field

from app.ingestion.store import create_pool
from app.retrieval.retriever import retrieve


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    k: int = Field(default=5, ge=1, le=50)
    source: str | None = None


class SearchResult(BaseModel):
    text: str
    heading_path: list[str]
    source: str
    chunk_index: int
    score: float


class SearchResponse(BaseModel):
    results: list[SearchResult]


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pool = create_pool()
    yield
    app.state.pool.close()


app = FastAPI(title="RunbookRAG API", lifespan=lifespan)


def get_conn() -> Iterator[psycopg.Connection]:
    with app.state.pool.connection() as conn:
        yield conn


@app.get("/")
def health_check():
    return {"status": "healthy"}


@app.post("/search", response_model=SearchResponse)
def search(payload: SearchRequest, conn: psycopg.Connection = Depends(get_conn)) -> SearchResponse:
    results = retrieve(conn, payload.query, k=payload.k, source=payload.source)
    return SearchResponse(
        results=[
            SearchResult(
                text=r.text,
                heading_path=r.heading_path,
                source=r.source,
                chunk_index=r.chunk_index,
                score=1 - r.distance,
            )
            for r in results
        ]
    )

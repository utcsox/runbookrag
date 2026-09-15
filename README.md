# RunbookRAG

A retrieval-augmented search API for troubleshooting runbooks. Runbooks are chunked on their heading structure, embedded with a local sentence-transformers model, and stored in Postgres/pgvector for semantic search.

## Architecture

```
markdown runbooks                query string
      │                               │
      ▼                               ▼
   Chunk                           Embed
(chunking.py)                  (embedder.py)
      │                               │
      ▼                               │
   Embed                              │
(embedder.py)                         │
      │                               │
      ▼          cosine distance      ▼
   Store  ─────────────────────►  Retrieve
(store.py,                     (retriever.py)
 pgvector)                            │
                                       ▼
                          POST /search (app/main.py)
```

Both branches share `embedder.py` — the same model embeds runbook chunks at ingestion time and the query at search time, so both live in the same vector space.

| Module | Responsibility |
|---|---|
| `app/ingestion/chunking.py` | Splits markdown on heading structure (not fixed-size windows), so each chunk carries a heading breadcrumb for context. Oversized sections are further split with configurable overlap, and splits never land inside a fenced code block. |
| `app/ingestion/embedder.py` | Turns text into 384-dim vectors via a local `sentence-transformers` model. |
| `app/ingestion/store.py` | All Postgres/pgvector access: schema creation, upsert (by a deterministic id, so re-ingesting a runbook never duplicates it), and cosine-distance nearest-neighbor search. |
| `app/retrieval/retriever.py` | Thin composition layer: embed a query, search the store, return ranked `RetrievedChunk` results. |
| `app/main.py` | FastAPI app exposing `POST /search`. |
| `scripts/ingest.py` | CLI entry point tying chunk → embed → store together for a file or directory of runbooks. |

**Key decisions:**

- **Heading-based chunking, not fixed-size windows.** A runbook's meaning lives in its section structure (Symptoms / Diagnose / Mitigation); splitting on headings keeps each chunk coherent, and a heading breadcrumb prefix keeps it meaningful once embedded in isolation.
- **Local embeddings over a hosted API.** No API key, no per-call cost, no network dependency at inference time — trading off against the quality ceiling of a larger hosted model, which is an acceptable trade for this project's scale.
- **`psycopg` (v3) directly, no ORM.** Matches the rest of the stack (no ORM anywhere else), and the schema is a single table — an ORM would add abstraction without a corresponding benefit here.
- **A connection pool for the API, a single connection for scripts/notebooks.** `app/main.py` uses `psycopg_pool.ConnectionPool` (opened once at FastAPI startup) because concurrent HTTP requests can't safely share one `psycopg.Connection`. A one-off script or notebook cell has no concurrency to worry about, so it just calls `connect()` directly.
- **Deterministic ids for upsert, not append-only inserts.** Each chunk's id is a hash of `source:chunk_index`, so re-running ingestion on an unchanged runbook overwrites its existing rows instead of duplicating them.

## Prerequisites

- [Docker](https://www.docker.com/) (for Postgres + pgvector)
- [uv](https://docs.astral.sh/uv/) (Python package/dependency manager)

## Setup

```bash
make setup
```

Runs pre-flight checks and creates the local virtual environment via `uv sync`.

## Start the database

```bash
docker compose up -d db
```

Wait for it to report healthy:

```bash
docker compose ps db
```

## Ingest the sample runbooks

`/search` only finds what's already stored, so seed the database once:

```bash
make ingest
```

Or run the script directly, against a single file or a directory of `.md` files:

```bash
uv run python scripts/ingest.py data/runbooks/gitlab
uv run python scripts/ingest.py data/runbooks/gitlab/redis-troubleshooting.md
```

This is safe to re-run — chunks are upserted, not duplicated.

## Run the API

```bash
uv run uvicorn app.main:app --reload
```

## Try it

```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "redis server wont respond to ping", "k": 3}'
```

Or open the interactive docs at [http://localhost:8000/docs](http://localhost:8000/docs) and try `POST /search` from there.

## Run the tests

```bash
uv run pytest
```

Requires the database to be running (`docker compose up -d db`) - several tests exercise the real database and embedding model rather than mocking them.

## Data persistence

Postgres data lives in a named Docker volume (`pgdata`) that survives `docker compose down` and container restarts. Only `make clean` (or `docker compose down -v` directly) deletes it, requiring the ingestion step to be re-run.

## Notebooks

`notebooks/01_ingestion_pipeline.ipynb` walks through the full pipeline (chunk → embed → store → retrieve) step by step, with inline inspection at each stage.

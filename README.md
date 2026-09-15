# RunbookRAG

A retrieval-augmented search API for troubleshooting runbooks. Runbooks are chunked on their heading structure, embedded with a local sentence-transformers model, and stored in Postgres/pgvector for semantic search.

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

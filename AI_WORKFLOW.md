# AI Workflow

## What this project does

RunbookRAG is a retrieval-augmented search API for SRE/DevOps troubleshooting runbooks. It takes a natural-language query (e.g. "redis server won't respond to ping") and returns the most relevant sections of real runbooks, ranked by semantic similarity.

The pipeline has four stages:

1. **Chunk** — markdown runbooks are split on their heading structure (not fixed-size windows), so each piece carries a heading breadcrumb for context and never splits inside a fenced code block.
2. **Embed** — each chunk is turned into a 384-dim vector using a local `sentence-transformers` model (`all-MiniLM-L6-v2`) — no API key, no per-call cost.
3. **Store** — chunks and vectors are upserted into Postgres/pgvector, keyed by a deterministic id so re-ingesting a runbook never duplicates it.
4. **Retrieve** — a `POST /search` FastAPI endpoint embeds the query and returns the nearest chunks by cosine distance, with a `score` field per result.

The sample corpus is six real GitLab SRE runbooks (Redis, Gitaly, Sidekiq, PgBouncer, Patroni/Postgres, Vault), pulled from GitLab's public, MIT-licensed `runbooks` repository. Everything runs locally: Postgres/pgvector in Docker Compose, embeddings on CPU, no external API dependency at inference time.

## Why I chose this project

The role emphasizes automating operational (DevOps/SRE) work. A RAG system over real incident-response runbooks is a direct example of that: it's the kind of tool that would actually get used during an on-call incident to surface the right procedure fast, rather than a generic demo. It also forced real system-design decisions — chunking strategy, embedding model choice, vector storage, connection management under concurrency — rather than being a thin wrapper around one API call.

## AI tools and models used

Claude Code (Claude Sonnet 5) was the primary development interface for the entire project, from the initial scaffold through the last bugfix. No other AI coding tool or IDE assistant was used.

For embeddings, the project uses `all-MiniLM-L6-v2` from the Sentence Transformers library — a local, open-source model that runs on CPU with no API key or per-call cost. It's used to embed both the runbook chunks at ingestion time and the query at search time, so both sides of the similarity search live in the same vector space.

## How AI was integrated into my workflow

The development pattern was conversational and iterative rather than "describe the whole project, generate it once":

- **Design decisions were discussed before implementation**, not assumed. For genuine forks in the road — local embeddings vs. a hosted API, `psycopg` vs. an ORM, a connection pool vs. a naive per-request connection, whether ingestion should be a script or an API endpoint — I was given a recommendation with the concrete trade-off, and made the call before code was written.
- **Scope was actively managed, not maximized.** Several times the reasonable next step (a `config.py`, an ingestion API endpoint) was proposed and explicitly deferred until there was a concrete reason for it, rather than building it because it seemed like good practice in the abstract.
- **Everything was verified against real infrastructure, not mocked.** Chunking was tested against the actual downloaded runbook markdown, not just hand-written fixtures. The embedding model was really downloaded and run. Every database interaction ran against a real Postgres/pgvector container. The `/search` endpoint was hit with real `curl` requests through a real running server, and the full Docker Compose stack was built and started end-to-end, not just assumed to work from reading the Dockerfile.
- **Commits were scoped and reviewed before being made** — each commit's file list was laid out and agreed on before staging, and the working tree was checked for unrelated in-progress files that shouldn't be swept in.
- **Unit and integration tests back every change, and run automatically in CI.** A GitHub Actions workflow runs the full test suite (and lint) against a real pgvector service container on every push and pull request, so regressions surface immediately rather than only when someone remembers to run tests locally.
- **A Jupyter notebook (`notebooks/01_ingestion_pipeline.ipynb`) was used alongside the production code to actually exercise the pipeline** — chunking real runbooks, generating embeddings, storing them, and querying them back — rather than trusting the code was correct from reading it. Inspecting real chunk output in the notebook directly drove two design changes to the chunker: reducing the default max chunk size from 3000 to 1500 characters, so pieces stayed focused enough to embed and retrieve well, and introducing a configurable `chunk_overlap` so context carried across a section's split boundaries instead of being lost.

## Where AI significantly helped

**Proportional architecture decisions across the whole build.** The connection-pooling design for the `/search` endpoint (a `psycopg_pool.ConnectionPool` opened once at FastAPI startup via a lifespan hook, rather than one shared connection reused unsafely across concurrent requests) was flagged and built deliberately once the project had an actual HTTP server, not before. The same discipline applied in reverse — a `config.py` was proposed and declined twice because nothing yet needed it, keeping the codebase's complexity matched to its actual requirements at each stage rather than front-loaded.

## Where AI-generated output required correction or debugging

**An unhelpful error message that needed refinement, then validation.** My first version of `connect()` in `app/ingestion/store.py` just called `psycopg.connect()` directly — if the database wasn't running, that failed with a bare "connection refused," technically correct but not helpful to whoever hit it next. After this was pointed out, I refined it:

```python
try:
    conn = psycopg.connect(url, autocommit=True)
except psycopg.OperationalError as e:
    raise psycopg.OperationalError(
        "Could not connect to Postgres. Is the database running? "
        "Start it with: docker compose up -d db"
    ) from e
```

I didn't just assume this fix worked — I validated it by deliberately stopping the database and re-running a Jupyter notebook cell that used it, confirming the actionable message actually appears as the final line of the traceback, the most visible part of any cell error.

**A silent data-corruption bug in the ingestion CLI, caught by testing the script itself, not just its functions.** `chunk_file()` stored a chunk's `source` field as `str(path)` verbatim. When I built `scripts/ingest.py` and tested it with a relative path after having earlier ingested the same files via an absolute-path notebook run, the same file produced two different deterministic ids — so instead of upserting, the ingestion silently doubled the stored chunk count (108 → 216). This only surfaced because I ran the actual script end-to-end against the real database with a different invocation style than before, rather than trusting that unit tests of the underlying functions were sufficient. Fixed by resolving to a canonical absolute path, with a regression test proving relative and absolute invocations of the same file now agree.

**A Docker build nobody had actually run.** The project had been developed and tested against `docker compose up -d db` (database only) for most of its history; the full `docker compose up` (app + db) had never been executed. When I finally ran it end-to-end, it exposed two real problems: a missing `.dockerignore` meant the 1.2GB local `.venv` was being copied into every build (stalling it for minutes), and the container's startup command silently re-downloaded the entire dev dependency group (jupyter, matplotlib, ruff — ~96 packages) at every start, because `uv run`'s own sync check didn't respect the `--no-dev` flag used at build time. Neither was visible from reading the Dockerfile — both only showed up from actually building and running the image.

The common thread across all of these: the bugs that mattered were the ones synthetic tests or a plausible-looking implementation wouldn't have caught, and they were found by insisting on running the real thing — the real model, the real database, the real Docker build — rather than accepting code that merely looked correct.

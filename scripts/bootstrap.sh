#!/usr/bin/env bash
set -euo pipefail

command -v uv >/dev/null 2>&1 || { echo "uv not found. Install: https://docs.astral.sh/uv/getting-started/installation/"; exit 1; }
command -v docker >/dev/null 2>&1 || echo "warning: docker not found — needed later for 'make up' (postgres/pgvector)"
[ -f .env ] || { cp .env.example .env; echo "created .env from .env.example"; }

uv sync

echo "ready. run: uv run uvicorn app.main:app --reload"

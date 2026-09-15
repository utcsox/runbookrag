"""Ingest markdown runbooks into the pgvector-backed Postgres database.

Usage:
    uv run python scripts/ingest.py data/runbooks/gitlab
    uv run python scripts/ingest.py data/runbooks/gitlab/redis-troubleshooting.md
    uv run python scripts/ingest.py --clear data/runbooks/gitlab
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.ingestion.chunking import chunk_file
from app.ingestion.embedder import embed_chunks
from app.ingestion.store import connect, count, ensure_schema, store_chunks


def _collect_paths(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if path.is_dir():
        return sorted(path.glob("*.md"))
    raise FileNotFoundError(f"No such file or directory: {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "path",
        type=Path,
        help="A markdown file, or a directory of .md files, to ingest",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Delete all existing rows from the chunks table before ingesting",
    )
    args = parser.parse_args()

    paths = _collect_paths(args.path)
    if not paths:
        print(f"No markdown files found under {args.path}")
        return 1

    chunks = [chunk for p in paths for chunk in chunk_file(p)]
    print(f"Chunked {len(paths)} file(s) into {len(chunks)} chunks")

    embedded = embed_chunks(chunks)

    conn = connect()
    ensure_schema(conn)

    if args.clear:
        conn.execute("TRUNCATE TABLE chunks")
        print("Cleared existing chunks")

    store_chunks(conn, embedded)

    print(f"Ingested {len(embedded)} chunks ({count(conn)} total in the table)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

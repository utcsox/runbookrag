"""Delete all rows from the chunks table (schema and container untouched).

Usage:
    uv run python scripts/reset_db.py
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.ingestion.store import connect, count, ensure_schema


def main() -> int:
    conn = connect()
    ensure_schema(conn)

    before = count(conn)
    conn.execute("TRUNCATE TABLE chunks")
    print(f"Cleared {before} chunk(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

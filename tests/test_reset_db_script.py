import subprocess
import sys
from pathlib import Path

import pytest

from app.ingestion.chunking import Chunk
from app.ingestion.embedder import embed_chunks
from app.ingestion.store import (
    connect,
    count,
    count_by_source,
    delete_by_source,
    ensure_schema,
    store_chunks,
)

SOURCE = "test-reset-db.md"


def _run_reset_db() -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "scripts/reset_db.py"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent,
        check=False,
    )


@pytest.fixture
def conn():
    connection = connect()
    ensure_schema(connection)
    delete_by_source(connection, SOURCE)

    yield connection

    delete_by_source(connection, SOURCE)
    connection.close()


def test_reset_db_clears_the_whole_table(conn):
    store_chunks(
        conn,
        embed_chunks([Chunk(text="unrelated", heading_path=[], source=SOURCE, chunk_index=0)]),
    )
    assert count_by_source(conn, SOURCE) == 1

    result = _run_reset_db()

    assert result.returncode == 0, result.stderr
    assert "Cleared" in result.stdout
    assert count(conn) == 0
    assert count_by_source(conn, SOURCE) == 0

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

RUNBOOK_PATH = Path(__file__).parent.parent / "data" / "runbooks" / "gitlab" / "gitaly-down.md"
SOURCE = str(RUNBOOK_PATH.resolve())
OTHER_SOURCE = "test-ingest-script-other.md"


def _run_ingest(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "scripts/ingest.py", *args],
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
    delete_by_source(connection, OTHER_SOURCE)

    yield connection

    delete_by_source(connection, SOURCE)
    delete_by_source(connection, OTHER_SOURCE)
    connection.close()


def test_ingest_script_stores_chunks_and_is_idempotent(conn):
    result = _run_ingest(str(RUNBOOK_PATH))
    assert result.returncode == 0, result.stderr
    first_count = count_by_source(conn, SOURCE)
    assert first_count > 0

    result = _run_ingest(str(RUNBOOK_PATH))
    assert result.returncode == 0, result.stderr
    assert count_by_source(conn, SOURCE) == first_count


def test_ingest_script_relative_and_absolute_paths_agree(conn):
    relative = str(Path("data") / "runbooks" / "gitlab" / "gitaly-down.md")
    _run_ingest(relative)
    after_relative = count_by_source(conn, SOURCE)

    _run_ingest(str(RUNBOOK_PATH))
    after_absolute = count_by_source(conn, SOURCE)

    assert after_relative == after_absolute > 0


def test_ingest_script_missing_path_exits_nonzero():
    result = _run_ingest("data/runbooks/does-not-exist.md")
    assert result.returncode != 0


def test_ingest_script_clear_flag_wipes_the_whole_table(conn):
    store_chunks(
        conn,
        embed_chunks(
            [Chunk(text="unrelated", heading_path=[], source=OTHER_SOURCE, chunk_index=0)]
        ),
    )
    assert count_by_source(conn, OTHER_SOURCE) == 1

    result = _run_ingest("--clear", str(RUNBOOK_PATH))
    assert result.returncode == 0, result.stderr

    assert count_by_source(conn, OTHER_SOURCE) == 0
    assert count(conn) == count_by_source(conn, SOURCE)

import sqlite3
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import db as db_module  # noqa: E402
import observability  # noqa: E402
import retrieval  # noqa: E402
from db import SCHEMA  # noqa: E402


@pytest.fixture
def memdb(monkeypatch):
    """An in-memory SQLite database wired into the app's get_db() singleton."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    # Mark the schema current so init_db() (run by the app lifespan in API tests)
    # treats it as up to date and does not drop the seeded tables.
    conn.execute(f"PRAGMA user_version = {db_module.SCHEMA_VERSION}")
    monkeypatch.setattr(db_module, "_conn", conn)
    retrieval.reset_index()
    observability._records.clear()
    yield conn
    retrieval.reset_index()
    observability._records.clear()
    conn.close()


def insert_document(conn, **kwargs):
    """Insert a document row, returning its id. Sensible defaults for omitted fields."""
    fields = {
        "filename": "doc.pdf",
        "rel_path": "ffu/doc.pdf",
        "doc_code": None,
        "doc_number": None,
        "doc_kind": "base",
        "is_revision": 0,
        "revision_label": None,
        "supersedes_id": None,
        "content": "",
    }
    fields.update(kwargs)
    cur = conn.execute(
        "INSERT INTO documents(filename, rel_path, doc_code, doc_number, doc_kind,"
        " is_revision, revision_label, supersedes_id, content)"
        " VALUES(:filename,:rel_path,:doc_code,:doc_number,:doc_kind,"
        ":is_revision,:revision_label,:supersedes_id,:content)",
        fields,
    )
    return cur.lastrowid


def insert_chunk(conn, document_id, ordinal, page, text, heading=None):
    cur = conn.execute(
        "INSERT INTO chunks(document_id, ordinal, page, heading, text) VALUES(?,?,?,?,?)",
        (document_id, ordinal, page, heading, text),
    )
    return cur.lastrowid

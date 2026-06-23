import sqlite3
import threading

from config import DB_PATH

SCHEMA_VERSION = 3

SCHEMA = """
CREATE TABLE documents(
  id INTEGER PRIMARY KEY,
  filename TEXT,
  rel_path TEXT,
  doc_code TEXT,
  doc_number TEXT,
  doc_kind TEXT,
  is_revision INTEGER DEFAULT 0,
  revision_label TEXT,
  supersedes_id INTEGER,
  summary TEXT,
  content TEXT
);
CREATE TABLE chunks(
  id INTEGER PRIMARY KEY,
  document_id INTEGER,
  ordinal INTEGER,
  page INTEGER,
  heading TEXT,
  text TEXT
);
CREATE TABLE embeddings(
  chunk_id INTEGER PRIMARY KEY,
  vector BLOB
);
CREATE TABLE overview_items(
  id INTEGER PRIMARY KEY,
  document_id INTEGER,
  category TEXT,
  text TEXT,
  source_page INTEGER,
  normalized_date TEXT
);
CREATE TABLE refs(
  id INTEGER PRIMARY KEY,
  source_document_id INTEGER,
  target_document_id INTEGER,
  ref_text TEXT,
  ref_type TEXT,
  page INTEGER,
  snippet TEXT
);
CREATE INDEX idx_chunks_doc ON chunks(document_id);
CREATE INDEX idx_overview_cat ON overview_items(category);
CREATE INDEX idx_refs_src ON refs(source_document_id);
CREATE INDEX idx_refs_tgt ON refs(target_document_id);
"""

_conn: sqlite3.Connection | None = None
write_lock = threading.Lock()


def get_db() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
    return _conn


def init_db() -> None:
    db = get_db()
    version = db.execute("PRAGMA user_version").fetchone()[0]
    if version != SCHEMA_VERSION:
        db.executescript(
            "DROP TABLE IF EXISTS overview_items;"
            "DROP TABLE IF EXISTS refs;"
            "DROP TABLE IF EXISTS documents;"
            "DROP TABLE IF EXISTS chunks;"
            "DROP TABLE IF EXISTS embeddings;"
        )
        db.executescript(SCHEMA)
        db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        db.commit()

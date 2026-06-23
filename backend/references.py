"""Cross-document reference graph.

Extracts explicit references between FFU documents and exposes them as a
navigable graph. Two reference layers are detected:

- ``handling``: document-to-document references phrased like "handling 13.1",
  "ritning 12.2", "bilaga 13.13" or "enligt 10.1". The captured handling code
  is resolved to another document by its ``doc_code``.
- ``drawing``: full drawing numbers like ``M-10.2-2001`` (matched against the
  ``doc_number`` column when present).

Edges are stored in the ``refs`` table and aggregated for the graph view.
"""

import logging
import re

from db import get_db, write_lock

logger = logging.getLogger(__name__)

# Anchored doc-to-doc reference: a referencing word followed by a handling code
# such as 13.1 or 10.2. Anchoring on the word avoids matching bare numbers,
# AMA codes and measurements.
HANDLING_RE = re.compile(
    r"(?:handling(?:en|ar|arna)?|ritning(?:en|ar|arna)?|bilaga|bilagor|"
    r"dokument(?:et)?|enligt|se|förteckning(?:en)?)"
    r"\s+(?:även\s+)?"
    r"(\d{1,2}\.\d{1,2})\b",
    re.IGNORECASE,
)

# Full drawing/document number, e.g. M-10.2-2001 or Z-51.1-2028.
DRAWING_RE = re.compile(r"\b([A-Z]-\d{2}\.\d-\d{4})\b")

SNIPPET_RADIUS = 60


def _normalize_code(code: str | None) -> str | None:
    """Normalize a handling code so '09.1' and '9.1' compare equal."""
    if not code:
        return None
    parts = code.strip().split(".")
    try:
        return ".".join(str(int(p)) for p in parts)
    except ValueError:
        return code.strip()


def _snippet(text: str, start: int, end: int) -> str:
    lo = max(0, start - SNIPPET_RADIUS)
    hi = min(len(text), end + SNIPPET_RADIUS)
    prefix = "…" if lo > 0 else ""
    suffix = "…" if hi < len(text) else ""
    return prefix + " ".join(text[lo:hi].split()) + suffix


def _build_registry(docs) -> tuple[dict[str, int], dict[str, int]]:
    """Map normalized handling codes and drawing numbers to a document id.

    When several documents share a handling code (a base and its revision),
    the base is preferred so edges point at the canonical document.
    """
    by_code: dict[str, int] = {}
    by_number: dict[str, int] = {}
    for d in docs:
        code = _normalize_code(d["doc_code"])
        if code:
            existing = by_code.get(code)
            if existing is None or d["doc_kind"] == "base":
                by_code[code] = d["id"]
        number = (d["doc_number"] or "").strip()
        if number:
            by_number.setdefault(number, d["id"])
    return by_code, by_number


def build_references() -> dict:
    """Scan all chunks for references and rebuild the ``refs`` table."""
    db = get_db()
    docs = db.execute(
        "SELECT id, filename, doc_code, doc_number, doc_kind FROM documents"
    ).fetchall()
    by_code, by_number = _build_registry(docs)
    own_code = {d["id"]: _normalize_code(d["doc_code"]) for d in docs}

    chunks = db.execute(
        "SELECT document_id, page, text FROM chunks ORDER BY document_id, ordinal"
    ).fetchall()

    # Deduplicate identical (source, target, ref_text) edges, keeping the first
    # page/snippet where the reference appears.
    seen: set[tuple[int, int, str]] = set()
    edges: list[tuple] = []
    unresolved = 0

    for ch in chunks:
        src = ch["document_id"]
        text = ch["text"] or ""

        for m in HANDLING_RE.finditer(text):
            code = _normalize_code(m.group(1))
            if not code:
                continue
            target = by_code.get(code)
            if target is None:
                unresolved += 1
                continue
            if target == src or code == own_code.get(src):
                continue
            key = (src, target, code)
            if key in seen:
                continue
            seen.add(key)
            edges.append(
                (src, target, code, "handling", ch["page"], _snippet(text, m.start(1), m.end(1)))
            )

        for m in DRAWING_RE.finditer(text):
            number = m.group(1)
            target = by_number.get(number)
            if target is None or target == src:
                continue
            # Skip edges between a document and its own base/revision sibling.
            tgt_code = own_code.get(target)
            if tgt_code is not None and tgt_code == own_code.get(src):
                continue
            key = (src, target, number)
            if key in seen:
                continue
            seen.add(key)
            edges.append(
                (src, target, number, "drawing", ch["page"], _snippet(text, m.start(1), m.end(1)))
            )

    with write_lock:
        try:
            db.execute("DELETE FROM refs")
            db.executemany(
                "INSERT INTO refs(source_document_id, target_document_id, ref_text,"
                " ref_type, page, snippet) VALUES(?,?,?,?,?,?)",
                edges,
            )
            db.commit()
        except Exception:
            db.rollback()
            raise

    return {"edges": len(edges), "unresolved": unresolved}


def graph() -> dict:
    """Return the full reference graph: nodes plus aggregated edges."""
    db = get_db()
    nodes = [
        {
            "id": d["id"],
            "filename": d["filename"],
            "doc_code": d["doc_code"],
            "doc_kind": d["doc_kind"],
        }
        for d in db.execute(
            "SELECT id, filename, doc_code, doc_kind FROM documents ORDER BY id"
        ).fetchall()
    ]
    rows = db.execute(
        "SELECT source_document_id AS source, target_document_id AS target,"
        " COUNT(*) AS count, MIN(page) AS page,"
        " GROUP_CONCAT(DISTINCT ref_text) AS labels"
        " FROM refs GROUP BY source_document_id, target_document_id"
    ).fetchall()
    edges = [
        {
            "source": r["source"],
            "target": r["target"],
            "count": r["count"],
            "page": r["page"],
            "labels": (r["labels"] or "").split(","),
        }
        for r in rows
    ]
    return {"nodes": nodes, "edges": edges}


def document_references(doc_id: int) -> dict:
    """Outgoing and incoming references for a single document, with detail."""
    db = get_db()
    outgoing = [
        dict(r)
        for r in db.execute(
            "SELECT r.target_document_id AS document_id, d.filename, r.ref_text,"
            " r.ref_type, r.page, r.snippet FROM refs r"
            " JOIN documents d ON d.id = r.target_document_id"
            " WHERE r.source_document_id = ? ORDER BY r.page, r.ref_text",
            (doc_id,),
        ).fetchall()
    ]
    incoming = [
        dict(r)
        for r in db.execute(
            "SELECT r.source_document_id AS document_id, d.filename, r.ref_text,"
            " r.ref_type, r.page, r.snippet FROM refs r"
            " JOIN documents d ON d.id = r.source_document_id"
            " WHERE r.target_document_id = ? ORDER BY r.page, r.ref_text",
            (doc_id,),
        ).fetchall()
    ]
    return {"outgoing": outgoing, "incoming": incoming}

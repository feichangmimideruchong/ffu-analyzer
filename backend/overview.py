import json
import logging
import re

import config
from db import get_db, write_lock

logger = logging.getLogger(__name__)

EXTRACT_PROMPT = """Extract tender overview items from this FFU document excerpt.
Return JSON: {"items":[{"category":"requirement|deadline|risk","text":"...","source_page":1,"normalized_date":"YYYY-MM-DD or null"}]}
Only include clear, actionable items. Use Swedish or English as in source. Max 8 items."""

DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def _extract_for_document(doc_id: int, filename: str, content: str) -> list[dict]:
    excerpt = content[:12000]
    try:
        resp = config.client().chat.completions.create(
            model=config.CHAT_MODEL,
            messages=[
                {"role": "system", "content": EXTRACT_PROMPT},
                {
                    "role": "user",
                    "content": f"Document: {filename}\n\n{excerpt}",
                },
            ],
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.choices[0].message.content or "{}")
        items = data.get("items") or []
        out = []
        for item in items[:8]:
            cat = item.get("category", "requirement")
            if cat not in ("requirement", "deadline", "risk"):
                cat = "requirement"
            text = (item.get("text") or "").strip()
            if not text:
                continue
            try:
                page = int(item.get("source_page") or 1)
            except (TypeError, ValueError):
                page = 1
            nd = item.get("normalized_date")
            if not nd:
                m = DATE_RE.search(text)
                nd = m.group(1) if m else None
            out.append(
                {
                    "document_id": doc_id,
                    "category": cat,
                    "text": text,
                    "source_page": page,
                    "normalized_date": nd,
                }
            )
        return out
    except Exception as e:
        logger.warning(f"Overview extract failed for {filename}: {e}")
        return []


def generate_overview() -> dict:
    db = get_db()
    docs = db.execute("SELECT id, filename, content FROM documents ORDER BY id").fetchall()
    # Slow OpenAI extraction happens outside the write lock so it doesn't block
    # ingestion or other writers for the duration of the network calls.
    all_items: list[dict] = []
    for doc in docs:
        items = _extract_for_document(doc["id"], doc["filename"], doc["content"])
        all_items.extend(items)
        logger.info(f"Overview: {len(items)} items from {doc['filename']}")
    with write_lock:
        db.execute("DELETE FROM overview_items")
        for item in all_items:
            db.execute(
                "INSERT INTO overview_items(document_id, category, text, source_page, normalized_date)"
                " VALUES(?,?,?,?,?)",
                (
                    item["document_id"],
                    item["category"],
                    item["text"],
                    item["source_page"],
                    item["normalized_date"],
                ),
            )
        db.commit()
    return {"items": len(all_items)}


def list_overview(category: str | None = None) -> list[dict]:
    db = get_db()
    if category:
        rows = db.execute(
            "SELECT o.id, o.document_id, o.category, o.text, o.source_page, o.normalized_date, "
            "d.filename FROM overview_items o JOIN documents d ON d.id = o.document_id "
            "WHERE o.category = ? ORDER BY o.normalized_date IS NULL, o.normalized_date, o.id",
            (category,),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT o.id, o.document_id, o.category, o.text, o.source_page, o.normalized_date, "
            "d.filename FROM overview_items o JOIN documents d ON d.id = o.document_id "
            "ORDER BY o.category, o.normalized_date IS NULL, o.normalized_date, o.id"
        ).fetchall()
    return [dict(r) for r in rows]

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import openpyxl
import pymupdf4llm

import config
from db import get_db, write_lock

logger = logging.getLogger(__name__)

DOC_NUMBER_RE = re.compile(r"[A-Z]-\d{2}\.\d-\d{4}")
DOC_CODE_RE = re.compile(r"^(\d{1,2}(?:\.\d+)?)")
REVISION_RE = re.compile(r"rev\.?\s*([\d-]{6,})|(KFU\s*\d+)|(Ändrings)", re.IGNORECASE)


def parse_metadata(filename: str) -> dict:
    code_match = DOC_CODE_RE.search(filename)
    number_match = DOC_NUMBER_RE.search(filename)
    rev_match = REVISION_RE.search(filename)
    label = None
    if rev_match:
        label = next((g for g in rev_match.groups() if g), None)
    is_kfu = "kfu" in filename.lower()
    is_revision = 1 if (rev_match and not is_kfu) or is_kfu else 0
    if is_kfu and not label:
        label = next((g for g in (rev_match.groups() if rev_match else ()) if g), "KFU")
    doc_kind = "amendment" if is_kfu else ("revision" if is_revision else "base")
    return {
        "doc_code": code_match.group(1) if code_match else None,
        "doc_number": number_match.group(0) if number_match else None,
        "is_revision": is_revision,
        "revision_label": label,
        "doc_kind": doc_kind,
    }


def link_revisions(db, doc_ids: list[int], documents: list[tuple]) -> None:
    """Link revision documents to their base via supersedes_id (same doc_code)."""
    by_code: dict[str, list[tuple[int, dict]]] = {}
    for doc_id, (path, _pages, meta, _content) in zip(doc_ids, documents):
        code = meta.get("doc_code")
        if not code or meta.get("doc_kind") == "amendment":
            continue
        by_code.setdefault(code, []).append((doc_id, meta))

    for _code, group in by_code.items():
        bases = [doc_id for doc_id, meta in group if meta.get("doc_kind") == "base"]
        revs = [doc_id for doc_id, meta in group if meta.get("doc_kind") == "revision"]
        if not revs:
            continue
        base_id = min(bases) if bases else None
        for rev_id in revs:
            if base_id:
                db.execute(
                    "UPDATE documents SET supersedes_id = ? WHERE id = ?",
                    (base_id, rev_id),
                )


def extract_pdf(path: Path) -> list[tuple[int, str]]:
    pages = pymupdf4llm.to_markdown(
        str(path), page_chunks=True, ignore_images=True, ignore_graphics=True
    )
    out = []
    for i, page in enumerate(pages):
        text = (page.get("text") or "").strip()
        if text:
            out.append((page.get("metadata", {}).get("page", i + 1), text))
    return out


def extract_xlsx(path: Path) -> list[tuple[int, str]]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    out = []
    for sheet_idx, ws in enumerate(wb.worksheets, start=1):
        lines = [f"# Sheet: {ws.title}"]
        for row in ws.iter_rows(values_only=True):
            cells = [str(c) for c in row if c is not None]
            if cells:
                lines.append(" | ".join(cells))
        text = "\n".join(lines).strip()
        if len(lines) > 1:
            out.append((sheet_idx, text))
    wb.close()
    return out


def extract(path: Path) -> list[tuple[int, str]]:
    if path.suffix.lower() == ".pdf":
        return extract_pdf(path)
    if path.suffix.lower() in (".xlsx", ".xlsm"):
        return extract_xlsx(path)
    return []


def chunk_page(text: str) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        if len(para) > config.CHUNK_CHARS * 2:
            for i in range(0, len(para), config.CHUNK_CHARS - config.CHUNK_OVERLAP):
                chunks.append(para[i : i + config.CHUNK_CHARS])
            continue
        if len(current) + len(para) + 2 > config.CHUNK_CHARS and current:
            chunks.append(current.strip())
            current = current[-config.CHUNK_OVERLAP :] + "\n\n" + para
        else:
            current = f"{current}\n\n{para}" if current else para
    if current.strip():
        chunks.append(current.strip())
    return chunks


def first_heading(text: str) -> str | None:
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            return line.lstrip("#").strip()[:120]
    return None


def embed_texts(texts: list[str]) -> list[bytes]:
    vectors: list[bytes] = []
    for i in range(0, len(texts), config.EMBED_BATCH):
        batch = texts[i : i + config.EMBED_BATCH]
        resp = config.client().embeddings.create(model=config.EMBED_MODEL, input=batch)
        for item in resp.data:
            vectors.append(np.asarray(item.embedding, dtype=np.float32).tobytes())
    return vectors


def run_pipeline() -> dict:
    db = get_db()
    paths = sorted(
        p for p in config.DATA_DIR.rglob("*") if p.suffix.lower() in (".pdf", ".xlsx", ".xlsm")
    )

    with ThreadPoolExecutor(max_workers=8) as pool:
        extracted = list(pool.map(lambda p: (p, _safe_extract(p)), paths))

    documents: list[tuple[Path, list[tuple[int, str]], dict, str]] = []
    chunk_rows: list[tuple[int, int, int, str | None, str]] = []
    chunk_texts: list[str] = []

    for doc_idx, (path, pages) in enumerate(extracted):
        if not pages:
            logger.info(f"Skipped (no text): {path.name}")
            continue
        meta = parse_metadata(path.name)
        content = "\n\n".join(text for _, text in pages)
        documents.append((path, pages, meta, content))
        ordinal = 0
        for page, text in pages:
            for chunk in chunk_page(text):
                chunk_rows.append((doc_idx, ordinal, page, first_heading(chunk), chunk))
                chunk_texts.append(chunk)
                ordinal += 1
        logger.info(f"Prepared {path.name} ({len(pages)} pages)")

    # Embed before replacing DB rows. If embedding fails, the old index remains usable.
    vectors = embed_texts(chunk_texts)

    with write_lock:
        try:
            db.execute("DELETE FROM embeddings")
            db.execute("DELETE FROM chunks")
            db.execute("DELETE FROM documents")

            doc_ids: list[int] = []
            for path, _pages, meta, content in documents:
                cur = db.execute(
                    "INSERT INTO documents(filename, rel_path, doc_code, doc_number, doc_kind,"
                    " is_revision, revision_label, content)"
                    " VALUES(?,?,?,?,?,?,?,?)",
                    (
                        path.name,
                        str(path.relative_to(config.DATA_DIR)),
                        meta["doc_code"],
                        meta["doc_number"],
                        meta["doc_kind"],
                        meta["is_revision"],
                        meta["revision_label"],
                        content,
                    ),
                )
                doc_ids.append(cur.lastrowid)

            link_revisions(db, doc_ids, documents)

            for (doc_idx, ordinal, page, heading, chunk), vector in zip(chunk_rows, vectors):
                cur = db.execute(
                    "INSERT INTO chunks(document_id, ordinal, page, heading, text) VALUES(?,?,?,?,?)",
                    (doc_ids[doc_idx], ordinal, page, heading, chunk),
                )
                db.execute(
                    "INSERT INTO embeddings(chunk_id, vector) VALUES(?,?)",
                    (cur.lastrowid, vector),
                )
            db.commit()
        except Exception:
            db.rollback()
            raise

    doc_count = db.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    chunk_count = db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    return {"documents": doc_count, "chunks": chunk_count}


def _safe_extract(path: Path) -> list[tuple[int, str]]:
    try:
        return extract(path)
    except Exception as e:
        logger.warning(f"Failed to extract {path.name}: {e}")
        return []

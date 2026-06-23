import math
import re
from collections import Counter

import numpy as np

import config
from db import get_db

_TOKEN_RE = re.compile(r"[0-9a-zåäöü][0-9a-zåäöü.\-:]*")


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class _Bm25:
    def __init__(self, corpus: list[list[str]]):
        self.corpus = corpus
        self.n = len(corpus)
        self.avgdl = sum(len(d) for d in corpus) / max(1, self.n)
        self.tf = [Counter(d) for d in corpus]
        df: Counter = Counter()
        for doc in corpus:
            df.update(set(doc))
        self.idf = {
            term: math.log(1 + (self.n - freq + 0.5) / (freq + 0.5))
            for term, freq in df.items()
        }

    def scores(self, query: str, k1: float = 1.5, b: float = 0.75) -> np.ndarray:
        terms = tokenize(query)
        scores = np.zeros(self.n, dtype=np.float32)
        for i in range(self.n):
            tf = self.tf[i]
            dl = len(self.corpus[i])
            total = 0.0
            for term in terms:
                freq = tf.get(term)
                if not freq:
                    continue
                idf = self.idf.get(term, 0.0)
                total += idf * (freq * (k1 + 1)) / (freq + k1 * (1 - b + b * dl / self.avgdl))
            scores[i] = total
        return scores


class _Index:
    def __init__(self):
        rows = get_db().execute(
            "SELECT c.id, c.document_id, c.page, c.heading, c.text, d.filename, "
            "d.is_revision, d.revision_label, d.supersedes_id, d.doc_kind, d.doc_code "
            "FROM chunks c JOIN documents d ON d.id = c.document_id ORDER BY c.id"
        ).fetchall()
        self.rows = rows
        emb_rows = get_db().execute(
            "SELECT chunk_id, vector FROM embeddings ORDER BY chunk_id"
        ).fetchall()
        emb_map = {r["chunk_id"]: np.frombuffer(r["vector"], dtype=np.float32) for r in emb_rows}
        if rows:
            matrix = np.vstack([emb_map[r["id"]] for r in rows])
            norms = np.linalg.norm(matrix, axis=1, keepdims=True)
            self.matrix = matrix / np.clip(norms, 1e-8, None)
        else:
            self.matrix = np.zeros((0, 1), dtype=np.float32)
        self.bm25 = _Bm25([tokenize(r["text"]) for r in rows])

    def search(self, query: str, k: int = config.TOP_K) -> list[dict]:
        if not self.rows:
            return []
        q_vec = np.asarray(
            config.client().embeddings.create(model=config.EMBED_MODEL, input=[query]).data[0].embedding,
            dtype=np.float32,
        )
        q_vec /= max(np.linalg.norm(q_vec), 1e-8)
        cosine = self.matrix @ q_vec
        bm25 = self.bm25.scores(query)

        pool = min(len(self.rows), max(k * 5, 25))
        vec_rank = np.argsort(-cosine)[:pool]
        bm_rank = np.argsort(-bm25)[:pool]

        rrf: dict[int, float] = {}
        for rank, idx in enumerate(vec_rank):
            rrf[idx] = rrf.get(idx, 0.0) + 1.0 / (config.RRF_K + rank)
        for rank, idx in enumerate(bm_rank):
            rrf[idx] = rrf.get(idx, 0.0) + 1.0 / (config.RRF_K + rank)

        top = sorted(rrf.items(), key=lambda kv: -kv[1])[:k]
        results = []
        for idx, score in top:
            row = self.rows[idx]
            results.append(_row_to_hit(row, score))
        return _expand_revision_hits(results, self.rows)


def _row_to_hit(row, score: float) -> dict:
    kind = row["doc_kind"] or ("revision" if row["is_revision"] else "base")
    label = _revision_label(row)
    return {
        "chunk_id": row["id"],
        "document_id": row["document_id"],
        "filename": row["filename"],
        "page": row["page"],
        "heading": row["heading"],
        "text": row["text"],
        "score": round(float(score), 4),
        "doc_kind": kind,
        "revision_label": label,
        "supersedes_id": row["supersedes_id"],
    }


def _revision_label(row) -> str | None:
    if row["doc_kind"] == "amendment":
        return row["revision_label"] or "amendment"
    if row["is_revision"]:
        return row["revision_label"] or "revision"
    if row["supersedes_id"]:
        return None
    return None


def _expand_revision_hits(hits: list[dict], all_rows) -> list[dict]:
    """If a hit is from a base doc, also include chunks from its revision (and vice versa)."""
    if not hits:
        return hits
    seen = {h["chunk_id"] for h in hits}
    doc_ids = {h["document_id"] for h in hits}
    db = get_db()
    extra: list[dict] = []

    for doc_id in list(doc_ids):
        row = db.execute(
            "SELECT id, doc_code, doc_kind, supersedes_id FROM documents WHERE id = ?",
            (doc_id,),
        ).fetchone()
        if not row or not row["doc_code"] or row["doc_kind"] == "amendment":
            continue
        related = db.execute(
            "SELECT id FROM documents WHERE doc_code = ? AND id != ? AND doc_kind != 'amendment'",
            (row["doc_code"], doc_id),
        ).fetchall()
        for rel in related:
            if rel["id"] in doc_ids:
                continue
            for chunk_row in all_rows:
                if chunk_row["document_id"] != rel["id"]:
                    continue
                if chunk_row["id"] in seen:
                    continue
                extra.append(_row_to_hit(chunk_row, hits[0]["score"] * 0.9))
                seen.add(chunk_row["id"])
                break
            doc_ids.add(rel["id"])

    return hits + extra[: max(2, len(hits) // 2)]


_index: _Index | None = None


def get_index() -> _Index:
    global _index
    if _index is None:
        _index = _Index()
    return _index


def reset_index() -> None:
    global _index
    _index = None


def search(query: str, k: int = config.TOP_K) -> list[dict]:
    return get_index().search(query, k)

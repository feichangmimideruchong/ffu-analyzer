import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

import chat
import ingest
import observability
import overview
import retrieval
from db import get_db, init_db

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app):
    init_db()
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


@app.post("/process")
def process():
    logger.info("Processing documents...")
    result = ingest.run_pipeline()
    retrieval.reset_index()
    logger.info(f"Done: {result}")
    return {"status": "ok", "count": result["documents"], **result}


@app.post("/chat")
def chat_endpoint(body: dict):
    return chat.run(body.get("message", ""), body.get("history", []))


@app.post("/chat/stream")
def chat_stream(body: dict):
    generator = chat.run_stream(body.get("message", ""), body.get("history", []))
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/stats")
def stats():
    return observability.stats()


@app.post("/overview/generate")
def overview_generate():
    logger.info("Generating overview...")
    result = overview.generate_overview()
    logger.info(f"Overview done: {result}")
    return {"status": "ok", **result}


@app.get("/overview")
def overview_list(category: str | None = None):
    return {"items": overview.list_overview(category)}


@app.get("/documents")
def documents():
    rows = get_db().execute(
        "SELECT id, filename, doc_code, doc_kind, is_revision, revision_label, supersedes_id "
        "FROM documents ORDER BY id"
    ).fetchall()
    return {"documents": [dict(r) for r in rows]}


@app.get("/document/{doc_id}")
def document(doc_id: int):
    db = get_db()
    row = db.execute(
        "SELECT id, filename, doc_code, doc_number, doc_kind, is_revision, "
        "revision_label, supersedes_id, content "
        "FROM documents WHERE id = ?",
        (doc_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found")
    chunks = db.execute(
        "SELECT page, heading, text FROM chunks WHERE document_id = ? ORDER BY ordinal",
        (doc_id,),
    ).fetchall()
    return {**dict(row), "chunks": [dict(c) for c in chunks]}

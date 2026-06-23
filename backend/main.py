import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

import chat
import ingest
import observability
import overview
import references
import retrieval
from db import get_db, init_db

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# Static SPA build, served in production (e.g. the Docker image). In local dev
# the Vite server serves the frontend and proxies /api here instead.
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app):
    init_db()
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

api = APIRouter(prefix="/api")


@api.get("/health")
def health():
    return {"status": "ok"}


@api.post("/process")
def process():
    logger.info("Processing documents...")
    result = ingest.run_pipeline()
    retrieval.reset_index()
    refs = references.build_references()
    logger.info(f"Done: {result}, references: {refs}")
    return {"status": "ok", "count": result["documents"], **result, "references": refs}


@api.post("/chat")
def chat_endpoint(body: dict):
    return chat.run(body.get("message", ""), body.get("history", []))


@api.post("/chat/stream")
def chat_stream(body: dict):
    generator = chat.run_stream(body.get("message", ""), body.get("history", []))
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@api.get("/stats")
def stats():
    return observability.stats()


@api.post("/overview/generate")
def overview_generate():
    logger.info("Generating overview...")
    result = overview.generate_overview()
    logger.info(f"Overview done: {result}")
    return {"status": "ok", **result}


@api.get("/overview")
def overview_list(category: str | None = None):
    return {"items": overview.list_overview(category)}


@api.post("/references/build")
def references_build():
    return {"status": "ok", **references.build_references()}


@api.get("/graph")
def graph():
    return references.graph()


@api.get("/document/{doc_id}/references")
def document_references(doc_id: int):
    return references.document_references(doc_id)


@api.get("/documents")
def documents():
    rows = get_db().execute(
        "SELECT id, filename, doc_code, doc_kind, is_revision, revision_label, supersedes_id "
        "FROM documents ORDER BY id"
    ).fetchall()
    return {"documents": [dict(r) for r in rows]}


@api.get("/document/{doc_id}")
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


app.include_router(api)

# Serve the built single-page app at the root when it exists (production image).
# `html=True` makes StaticFiles fall back to index.html for client-side routes.
if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="spa")

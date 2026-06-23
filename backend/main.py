import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import chat
import ingest
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


@app.get("/documents")
def documents():
    rows = get_db().execute(
        "SELECT id, filename, doc_code, is_revision, revision_label "
        "FROM documents ORDER BY id"
    ).fetchall()
    return {"documents": [dict(r) for r in rows]}

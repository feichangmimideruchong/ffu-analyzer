import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent

load_dotenv(ROOT_DIR / ".env")

CHAT_MODEL = os.environ.get("CHAT_MODEL", "gpt-5.4")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "text-embedding-3-small")
VISION_MODEL = os.environ.get("VISION_MODEL", "gpt-4.1-mini")

DATA_DIR = BASE_DIR / "data"
DB_PATH = BASE_DIR / "ffu.db"

# Chunking is char-based (language-agnostic); ~4 chars per token.
CHUNK_CHARS = 2000
CHUNK_OVERLAP = 400
EMBED_BATCH = 128

TOP_K = 8
RRF_K = 60

_client: OpenAI | None = None


def client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    return _client

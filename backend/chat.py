import json

import config
import retrieval
from db import get_db
from prompts import SYSTEM_PROMPT

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search",
            "description": "Hybrid semantic + keyword search over the FFU documents. "
            "Returns the most relevant chunks with their document id and page.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_document",
            "description": "Read the full text of one FFU document by its database id.",
            "parameters": {
                "type": "object",
                "properties": {"document_id": {"type": "integer"}},
                "required": ["document_id"],
            },
        },
    },
]


def _document_catalog() -> str:
    rows = get_db().execute(
        "SELECT id, filename, is_revision FROM documents ORDER BY id"
    ).fetchall()
    lines = []
    for row in rows:
        tag = " (revision)" if row["is_revision"] else ""
        lines.append(f"{row['id']}: {row['filename']}{tag}")
    return "\n".join(lines)


def _run_search(query: str) -> str:
    hits = retrieval.search(query)
    if not hits:
        return "No results. The document index may be empty (run Process FFU)."
    blocks = []
    for hit in hits:
        snippet = hit["text"][:1200]
        blocks.append(
            f"[[{hit['document_id']}:{hit['page']}]] {hit['filename']}"
            f" (score {hit['score']})\n{snippet}"
        )
    return "\n\n---\n\n".join(blocks)


def _read_document(document_id: int) -> str:
    row = get_db().execute(
        "SELECT content FROM documents WHERE id = ?", (document_id,)
    ).fetchone()
    return row["content"] if row else "Document not found."


def _dispatch(name: str, args: dict) -> str:
    if name == "search":
        return _run_search(args.get("query", ""))
    if name == "read_document":
        return _read_document(args["document_id"])
    return f"Unknown tool: {name}"


def run(message: str, history: list[dict]) -> dict:
    system = {
        "role": "system",
        "content": SYSTEM_PROMPT + "\n\nAvailable documents:\n" + _document_catalog(),
    }
    messages = [system, *history, {"role": "user", "content": message}]
    try:
        for _ in range(10):
            resp = config.client().chat.completions.create(
                model=config.CHAT_MODEL, messages=messages, tools=TOOLS, tool_choice="auto"
            )
            msg = resp.choices[0].message
            if not msg.tool_calls:
                return {"response": msg.content or ""}
            messages.append(msg.model_dump(exclude_none=True))
            for call in msg.tool_calls:
                args = json.loads(call.function.arguments or "{}")
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": _dispatch(call.function.name, args),
                    }
                )
        return {"response": "Stopped after 10 tool iterations."}
    except Exception as e:
        return {"response": f"Error: {e}"}

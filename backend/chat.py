import json
import time

import config
import observability
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
        "SELECT id, filename, doc_kind, is_revision, revision_label, supersedes_id "
        "FROM documents ORDER BY id"
    ).fetchall()
    lines = []
    for row in rows:
        tags = []
        if row["doc_kind"] == "amendment":
            tags.append("AMENDMENT")
        elif row["is_revision"]:
            tags.append(f"REVISION {row['revision_label'] or ''}".strip())
        if row["supersedes_id"]:
            tags.append(f"supersedes doc {row['supersedes_id']}")
        tag = f" [{', '.join(tags)}]" if tags else ""
        lines.append(f"{row['id']}: {row['filename']}{tag}")
    return "\n".join(lines)


def _format_hit(hit: dict) -> str:
    snippet = hit["text"][:1200]
    status = hit.get("doc_kind", "base").upper()
    if hit.get("revision_label"):
        status += f" ({hit['revision_label']})"
    if hit.get("supersedes_id"):
        status += f", supersedes doc {hit['supersedes_id']}"
    return (
        f"[[{hit['document_id']}:{hit['page']}]] {hit['filename']} [{status}]"
        f" (score {hit['score']})\n{snippet}"
    )


def _run_search(query: str, metrics: dict) -> str:
    start = time.perf_counter()
    hits = retrieval.search(query)
    metrics["search_ms"] = metrics.get("search_ms", 0.0) + (time.perf_counter() - start) * 1000
    metrics["hits"] = metrics.get("hits", 0) + len(hits)
    if not hits:
        return "No results. The document index may be empty (run Process FFU)."
    return "\n\n---\n\n".join(_format_hit(h) for h in hits)


def _read_document(document_id: int) -> str:
    row = get_db().execute(
        "SELECT content FROM documents WHERE id = ?", (document_id,)
    ).fetchone()
    return row["content"] if row else "Document not found."


def _dispatch(name: str, args: dict, metrics: dict) -> str:
    if name == "search":
        return _run_search(args.get("query", ""), metrics)
    if name == "read_document":
        return _read_document(args["document_id"])
    return f"Unknown tool: {name}"


def _build_messages(message: str, history: list[dict]) -> list[dict]:
    system = {
        "role": "system",
        "content": SYSTEM_PROMPT + "\n\nAvailable documents:\n" + _document_catalog(),
    }
    return [system, *history, {"role": "user", "content": message}]


def run(message: str, history: list[dict]) -> dict:
    messages = _build_messages(message, history)
    metrics: dict = {}
    started = time.perf_counter()
    iterations = 0
    try:
        for _ in range(10):
            iterations += 1
            gen_start = time.perf_counter()
            resp = config.client().chat.completions.create(
                model=config.CHAT_MODEL, messages=messages, tools=TOOLS, tool_choice="auto"
            )
            metrics["generation_ms"] = (
                metrics.get("generation_ms", 0.0) + (time.perf_counter() - gen_start) * 1000
            )
            msg = resp.choices[0].message
            if not msg.tool_calls:
                _record(metrics, started, iterations)
                return {"response": msg.content or ""}
            messages.append(msg.model_dump(exclude_none=True))
            for call in msg.tool_calls:
                args = json.loads(call.function.arguments or "{}")
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": _dispatch(call.function.name, args, metrics),
                    }
                )
        _record(metrics, started, iterations)
        return {"response": "Stopped after 10 tool iterations."}
    except Exception as e:
        return {"response": f"Error: {e}"}


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


def run_stream(message: str, history: list[dict]):
    """Yield Server-Sent Events. Streams answer tokens; emits status during tool calls."""
    messages = _build_messages(message, history)
    metrics: dict = {}
    started = time.perf_counter()
    iterations = 0
    try:
        for _ in range(10):
            iterations += 1
            gen_start = time.perf_counter()
            stream = config.client().chat.completions.create(
                model=config.CHAT_MODEL,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                stream=True,
            )
            content_parts: list[str] = []
            tool_calls: dict[int, dict] = {}
            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta.content:
                    content_parts.append(delta.content)
                    yield _sse({"type": "token", "text": delta.content})
                for tc in delta.tool_calls or []:
                    slot = tool_calls.setdefault(tc.index, {"id": "", "name": "", "args": ""})
                    if tc.id:
                        slot["id"] = tc.id
                    if tc.function and tc.function.name:
                        slot["name"] += tc.function.name
                    if tc.function and tc.function.arguments:
                        slot["args"] += tc.function.arguments
            metrics["generation_ms"] = (
                metrics.get("generation_ms", 0.0) + (time.perf_counter() - gen_start) * 1000
            )

            if not tool_calls:
                _record(metrics, started, iterations)
                yield _sse({"type": "done"})
                return

            messages.append(
                {
                    "role": "assistant",
                    "content": "".join(content_parts) or None,
                    "tool_calls": [
                        {
                            "id": s["id"],
                            "type": "function",
                            "function": {"name": s["name"], "arguments": s["args"]},
                        }
                        for s in tool_calls.values()
                    ],
                }
            )
            for s in tool_calls.values():
                yield _sse({"type": "status", "text": f"Running {s['name']}\u2026"})
                args = json.loads(s["args"] or "{}")
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": s["id"],
                        "content": _dispatch(s["name"], args, metrics),
                    }
                )
        _record(metrics, started, iterations)
        yield _sse({"type": "done"})
    except Exception as e:
        yield _sse({"type": "error", "text": str(e)})


def _record(metrics: dict, started: float, iterations: int) -> None:
    observability.record(
        latency_ms=(time.perf_counter() - started) * 1000,
        stages={
            "search_ms": metrics.get("search_ms", 0.0),
            "generation_ms": metrics.get("generation_ms", 0.0),
        },
        hits=metrics.get("hits", 0),
        tool_iterations=iterations,
    )

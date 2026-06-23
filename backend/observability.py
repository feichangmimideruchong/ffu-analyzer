import threading
from collections import deque

_lock = threading.Lock()
_records: deque[dict] = deque(maxlen=100)


def record(latency_ms: float, stages: dict[str, float], hits: int, tool_iterations: int) -> None:
    with _lock:
        _records.append(
            {
                "latency_ms": round(latency_ms, 1),
                "stages": {k: round(v, 1) for k, v in stages.items()},
                "hits": hits,
                "not_found": hits == 0,
                "tool_iterations": tool_iterations,
            }
        )


def stats() -> dict:
    with _lock:
        records = list(_records)
    n = len(records)
    if n == 0:
        return {"count": 0}
    stage_keys: set[str] = set()
    for r in records:
        stage_keys.update(r["stages"].keys())
    return {
        "count": n,
        "avg_latency_ms": round(sum(r["latency_ms"] for r in records) / n, 1),
        "avg_stage_ms": {
            k: round(sum(r["stages"].get(k, 0.0) for r in records) / n, 1) for k in stage_keys
        },
        "not_found_rate": round(sum(1 for r in records if r["not_found"]) / n, 3),
        "recent": records[-10:][::-1],
    }

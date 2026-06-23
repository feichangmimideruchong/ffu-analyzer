"""Evaluation harness for the FFU Analyzer.

Measures two things over a hand-built Q&A set (``qa.json``):

1. Retrieval quality — hit@k: does the expected source document appear in the
   top-k hybrid search results?
2. Answer correctness — an LLM-as-judge scores the chat answer against a set of
   expected points (0..1), grounded and citation-aware. Note: the judge uses the
   same model family as the assistant, so scores carry a known self-grading bias
   and should be read as a relative signal, not an absolute ground truth.

Run from the ``backend`` directory:

    ./venv/bin/python eval/run_eval.py --k 8

Requires a processed index (run Process FFU first) and OPENAI_API_KEY.
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import chat  # noqa: E402
import config  # noqa: E402
import retrieval  # noqa: E402

QA_PATH = Path(__file__).resolve().parent / "qa.json"

JUDGE_PROMPT = """You are grading an answer from an FFU (Swedish construction \
tender) assistant.

Question:
{question}

Expected key points (the answer is correct if it covers these, in any wording \
or language):
{points}

Assistant answer:
{answer}

Score how well the answer covers the expected points and whether it is factually \
consistent. Return JSON only:
{{"score": <float 0..1>, "covered": <true|false>, "reason": "<one sentence>"}}
A score of 1.0 means all key points are present and correct; 0.0 means missing \
or wrong. Ignore citation markers like [[3:5]] when judging wording."""


def load_qa() -> list[dict]:
    return json.loads(QA_PATH.read_text(encoding="utf-8"))


def hit_at_k(question: str, expected_sources: list[str], k: int) -> tuple[bool, list[str]]:
    hits = retrieval.search(question, k)[:k]
    filenames = [h["filename"] for h in hits]
    if not expected_sources:
        return False, filenames
    matched = all(
        any(src.lower() in fn.lower() for fn in filenames) for src in expected_sources
    )
    return matched, filenames


def judge(question: str, points: list[str], answer: str) -> dict:
    prompt = JUDGE_PROMPT.format(
        question=question,
        points="\n".join(f"- {p}" for p in points),
        answer=answer,
    )
    resp = config.client().chat.completions.create(
        model=config.CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    try:
        return json.loads(resp.choices[0].message.content or "{}")
    except json.JSONDecodeError:
        return {"score": 0.0, "covered": False, "reason": "judge returned invalid JSON"}


def _clamp_score(value) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _as_bool(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes")
    return bool(value)


def main() -> None:
    parser = argparse.ArgumentParser(description="FFU Analyzer eval harness")
    parser.add_argument("--k", type=int, default=config.TOP_K, help="hit@k cutoff")
    parser.add_argument("--limit", type=int, default=0, help="only run first N questions")
    parser.add_argument("--out", default=str(Path(__file__).resolve().parent / "report.json"))
    args = parser.parse_args()

    qa = load_qa()
    if args.limit:
        qa = qa[: args.limit]

    results = []
    for item in qa:
        started = time.perf_counter()
        hit, filenames = hit_at_k(item["question"], item["expected_sources"], args.k)
        answer = chat.run(item["question"], []).get("response", "")
        verdict = judge(item["question"], item["expected_points"], answer)
        elapsed = (time.perf_counter() - started) * 1000
        results.append(
            {
                "id": item["id"],
                "question": item["question"],
                "hit_at_k": hit,
                "top_filenames": filenames,
                "score": _clamp_score(verdict.get("score", 0.0)),
                "covered": _as_bool(verdict.get("covered", False)),
                "reason": verdict.get("reason", ""),
                "latency_ms": round(elapsed, 1),
                "answer": answer,
            }
        )
        flag = "✓" if hit else "✗"
        print(
            f"[{flag} hit@{args.k}] {item['id']:<16} "
            f"score={results[-1]['score']:.2f} ({verdict.get('reason', '')[:70]})"
        )

    n = len(results)
    summary = {
        "count": n,
        "hit_at_k": args.k,
        "hit_rate": round(sum(r["hit_at_k"] for r in results) / n, 3) if n else 0.0,
        "avg_score": round(sum(r["score"] for r in results) / n, 3) if n else 0.0,
        "covered_rate": round(sum(r["covered"] for r in results) / n, 3) if n else 0.0,
        "avg_latency_ms": round(sum(r["latency_ms"] for r in results) / n, 1) if n else 0.0,
    }
    print("\n=== Summary ===")
    for key, value in summary.items():
        print(f"{key}: {value}")

    Path(args.out).write_text(
        json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nReport written to {args.out}")


if __name__ == "__main__":
    main()

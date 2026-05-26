"""
eval/run_eval.py

Batch evaluation runner - loops through either:
  (a) the saved test_set.json  (benchmark mode)
  (b) the last N un-scored chat queries from question_history  (live mode)

Each row: calls ask_question() -> passes result to judge -> saves to SQLite.

Usage (standalone):
    python -m eval.run_eval --mode testset
    python -m eval.run_eval --mode live --n 10
"""

import time
import argparse
from pipeline.indexer import load_state
from generation.generator import ask_question
from eval.judge import score
from pipeline.db import (
    save_eval_score, get_recent_queries
)


def _chunk_texts(top_docs: list[dict]) -> list[str]:
    """Extract plain text from the top_docs returned by ask_question."""
    return [d.get("text", "") for d in top_docs if d.get("text")]


def run_on_test_set(path: str = "eval/test_set.json", delay: float = 6.0):
    """Score every question in the saved test set."""
    import json, os
    if not os.path.exists(path):
        print(f"[run_eval] Test set not found at {path}")
        print("  Run:  python -m eval.test_generator  first.")
        return []

    with open(path, encoding="utf-8") as f:
        test_set = json.load(f)

    print(f"[run_eval] Scoring {len(test_set)} test-set questions ")
    results = []

    for i, item in enumerate(test_set):
        query        = item["question"]
        ground_truth = item.get("ground_truth", "")
        doc_id       = item.get("doc_id") or None

        print(f"\n[{i+1}/{len(test_set)}] Q: {query[:80]} ")

        try:
            answer, top_docs, _, _ = ask_question(query, doc_id=doc_id)
        except Exception as e:
            print(f"  ask_question failed: {e}")
            time.sleep(delay)
            continue

        chunks = _chunk_texts(top_docs)
        scores = score(query, answer, chunks)

        print(f"  F={scores['faithfulness']:.2f}  "
              f"R={scores['relevancy']:.2f}  "
              f"CR={scores['context_recall']:.2f}")
        print(f"  Reasoning: {scores['reasoning']}")

        save_eval_score(
            query=query,
            answer=answer,
            chunks=chunks,
            faithfulness=scores["faithfulness"],
            relevancy=scores["relevancy"],
            context_recall=scores["context_recall"],
            reasoning=scores["reasoning"],
            scope=item.get("pdf", "All PDFs"),
        )
        results.append({**item, **scores})

        # Delay keeps us inside Groq free-tier limits
        time.sleep(delay)

    print(f"\n[run_eval] Done - {len(results)} rows saved to SQLite.")
    return results


def run_on_recent_queries(n: int = 10, delay: float = 6.0):
    """Score the last N chat queries that haven't been evaluated yet."""
    recent = get_recent_queries(limit=n)

    if not recent:
        print("[run_eval] No un-scored queries found in question_history.")
        return []

    print(f"[run_eval] Scoring {len(recent)} recent un-scored queries ")
    results = []

    for i, item in enumerate(recent):
        query = item["query"]
        scope = item.get("scope", "All PDFs")

        print(f"\n[{i+1}/{len(recent)}] Q: {query[:80]} ")

        try:
            answer, top_docs, _, _ = ask_question(query)
        except Exception as e:
            print(f"  ask_question failed: {e}")
            time.sleep(delay)
            continue

        chunks = _chunk_texts(top_docs)
        scores = score(query, answer, chunks)

        print(f"  F={scores['faithfulness']:.2f}  "
              f"R={scores['relevancy']:.2f}  "
              f"CR={scores['context_recall']:.2f}")

        save_eval_score(
            query=query,
            answer=answer,
            chunks=chunks,
            faithfulness=scores["faithfulness"],
            relevancy=scores["relevancy"],
            context_recall=scores["context_recall"],
            reasoning=scores["reasoning"],
            scope=scope,
        )
        results.append(scores)
        time.sleep(delay)

    print(f"\n[run_eval] Done - {len(results)} rows saved to SQLite.")
    return results


if __name__ == "__main__":
    load_state()
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["testset", "live"], default="live")
    parser.add_argument("--n",    type=int, default=10,
                        help="Number of recent queries to score (live mode only)")
    args = parser.parse_args()

    if args.mode == "testset":
        run_on_test_set()
    else:
        run_on_recent_queries(n=args.n)

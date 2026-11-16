"""Explicitly opt-in, manual real-provider check. Never run in CI.

Usage (only with non-sensitive sample data and an approved provider):
  LLM_ENABLED=1 LLM_EXTERNAL_APPROVED=1 LLM_API_KEY=... LLM_MODEL=... \
    python -m eval.run_live_answers --execute

Avoid writing live model responses to disk or logs: even synthetic examples may
teach poor habits around sending private customer runbooks to providers.
"""

import argparse
import os

from app.ai import HybridRetriever
from app.llm_answer import generate_grounded
from app.search import Index, load_chunks
from eval.run_answers_eval import CASES


def main():
    parser = argparse.ArgumentParser(description="Manual, opt-in grounded model check")
    parser.add_argument("--execute", action="store_true", help="Actually call external provider")
    args = parser.parse_args()
    if not args.execute:
        raise SystemExit("Not calling a provider. Specify --execute and explicit environment opt-in.")
    if os.getenv("LLM_ENABLED") != "1" or os.getenv("LLM_EXTERNAL_APPROVED") != "1":
        raise SystemExit("Set LLM_ENABLED=1 and LLM_EXTERNAL_APPROVED=1 after data review.")
    import json

    examples = json.loads(CASES.read_text(encoding="utf-8"))
    retriever = HybridRetriever(Index(load_chunks()))
    generated = 0
    fallback = 0
    for case in examples:
        hit = retriever.search(case["question"], case["tenant"])
        if hit is None:
            fallback += 1
            continue
        outcome = generate_grounded(case["question"], hit.chunk)
        if outcome.mode == "generated":
            generated += 1
        else:
            fallback += 1
    print(f"Manual run: {generated} validated extracts, {fallback} fallback/not-found")
    print("Not a semantic correctness guarantee; provider calls were manual, not CI.")


if __name__ == "__main__":
    main()

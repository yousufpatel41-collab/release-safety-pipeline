"""Offline deterministic fake-provider evaluation. Does not contact an LLM API.

Run: python -m eval.run_answers_eval
"""

import json
from pathlib import Path

from app.ai import HybridRetriever
from app.llm_answer import FakeLLM, check_generated
from app.search import Index, load_chunks

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "eval" / "answers.json"


def run() -> dict:
    tests = json.loads(CASES.read_text(encoding="utf-8"))
    retriever = HybridRetriever(Index(load_chunks()))
    fake = FakeLLM()
    failures = []
    for case in tests:
        hit = retriever.search(case["question"], case["tenant"])
        if hit is None:
            failures.append((case["question"], "retrieval_none"))
            continue
        if hit.chunk.id != case["expected_source"]:
            failures.append((case["question"], "wrong_source"))
            continue
        generated = fake.generate(case["question"], hit.chunk)
        if not check_generated(generated, hit.chunk):
            failures.append((case["question"], "citation_check_failed"))
        elif case["must_contain"].lower() not in generated.lower():
            failures.append((case["question"], "required_phrase_missing"))
        elif case["must_not_contain"].lower() in generated.lower():
            failures.append((case["question"], "prohibited_phrase_present"))
    return {"cases": len(tests), "passed": len(tests) - len(failures), "failures": failures}


def main():
    result = run()
    print(f'Offline FakeLLM checks: {result["passed"]}/{result["cases"]}')
    for question, issue in result["failures"]:
        print(f'- {question!r}: {issue}')
    if result["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

# Optional source-grounded answer evaluation

- **Offline test:** 15/15 synthetic questions passed (`python -m eval.run_answers_eval`).
- **Method:** `FakeLLM` deterministically selects an exact sentence from the source. This checks retrieval, citation validation and source selection, **not** the performance or factual reasoning of a real model.
- **Security/adversarial unit tests:** reject missing/wrong citations, negation changes, added instructions, edited numbers, hostile source content, long responses and provider exceptions.
- **Live provider:** **Not tested**. This is optional, off by default, and requires explicit data-transfer approval.
- **Real-world safety:** **Not measured**. Strict quotes reduce the room for invented facts but do not prove that retrieved material is trustworthy or relevant.

A sample of the test fixtures is kept in [`eval/answers.json`](../eval/answers.json). Do not mistake these deterministic checks for a live LLM benchmark.

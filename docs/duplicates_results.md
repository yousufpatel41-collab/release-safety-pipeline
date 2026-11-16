# Duplicate-ticket evaluation

Synthetic data only. These scores do **not** estimate real incident deduplication quality.
The threshold was selected using only calibration cases; test cases are incident-group-disjoint.
Ticket history is a fixed unsupervised retrieval index, not labelled training data.

Calibration questions: 15; held-out test questions: 16.
Selected cosine threshold: **0.40**.

| Split | TP | FP | TN | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Calibration | 9 | 1 | 5 | 0 | 0.900 | 1.000 | 0.947 |
| Held-out test | 10 | 0 | 6 | 0 | 1.000 | 1.000 | 1.000 |

## Misclassified cases (incident group, tenant, type, highest score)

**Calibration:**
- `new_workflow_g` / `globex`: FP, similarity=0.4207
**Held-out test:**
- None on this small synthetic sample

## Limits

- This is a small, hand-written, synthetic sample, not a field accuracy benchmark.
- Similarity cannot prove that two tickets have the same underlying incident.
- Duplicate flags only recommend **human review**; tickets are never merged.
- Additional real-world evaluation and time-based incident grouping are required.

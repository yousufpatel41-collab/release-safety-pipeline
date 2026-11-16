"""Choose threshold on calibration; report held-out data separately.

Run: python -m eval.run_duplicates_eval
All incidents in the test questions are disjoint from calibration questions.
These are synthetic data: metrics are not performance estimates for real customers.
"""

import json
from pathlib import Path

from app.duplicates import DuplicateFinder, load_tickets

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "eval" / "duplicates.json"
OUTPUT = ROOT / "docs" / "duplicates_results.md"


def evaluate(cases: list[dict], finder: DuplicateFinder) -> dict:
    counts = {'tp': 0, 'fp': 0, 'tn': 0, 'fn': 0}
    wrong = []
    for case in cases:
        result = finder.find(case['text'], case['tenant'])
        pred = result['possible_duplicate']
        actual = case['duplicate']
        kind = 'tp' if pred and actual else 'fp' if pred else 'fn' if actual else 'tn'
        counts[kind] += 1
        if pred != actual:
            wrong.append((case['incident_group'], case['tenant'], kind,
                          result['matches'][0]['score'] if result['matches'] else 0))
    tp, fp, fn = counts['tp'], counts['fp'], counts['fn']
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {**counts, 'precision': precision, 'recall': recall, 'f1': f1, 'wrong': wrong}


def run() -> tuple[float, dict, dict]:
    data = json.loads(DATA.read_text(encoding='utf-8'))
    groups_cal = {x['incident_group'] for x in data['calibration']}
    groups_test = {x['incident_group'] for x in data['test']}
    if groups_cal & groups_test:
        raise ValueError('Evaluation split reuses an incident group')
    tickets = load_tickets()
    # Candidate values are fixed in advance. Never use the test split to select a cutoff.
    candidates = [round(x / 100, 2) for x in range(20, 86, 5)]
    scored = [(t, evaluate(data['calibration'], DuplicateFinder(tickets, t))) for t in candidates]
    threshold, cal = max(scored, key=lambda x: (x[1]['f1'], x[1]['precision'], x[0]))
    test = evaluate(data['test'], DuplicateFinder(tickets, threshold))
    return threshold, cal, test


def main() -> None:
    threshold, cal, test = run()
    from app.duplicates import DUPLICATE_THRESHOLD
    if threshold != DUPLICATE_THRESHOLD:
        raise SystemExit(f'Configured cutoff {DUPLICATE_THRESHOLD} != calibration {threshold}')
    lines = [
        '# Duplicate-ticket evaluation', '',
        'Synthetic data only. These scores do **not** estimate real incident deduplication quality.',
        'The threshold was selected using only calibration cases; test cases are incident-group-disjoint.',
        'Ticket history is a fixed unsupervised retrieval index, not labelled training data.', '',
        f'Calibration questions: {sum(cal[k] for k in ("tp", "fp", "tn", "fn"))}; '
        f'held-out test questions: {sum(test[k] for k in ("tp", "fp", "tn", "fn"))}.',
        f'Selected cosine threshold: **{threshold:.2f}**.', '',
        '| Split | TP | FP | TN | FN | Precision | Recall | F1 |',
        '|---|---:|---:|---:|---:|---:|---:|---:|',
    ]
    for label, stats in [('Calibration', cal), ('Held-out test', test)]:
        lines.append(f'| {label} | {stats["tp"]} | {stats["fp"]} | {stats["tn"]} | '
                     f'{stats["fn"]} | {stats["precision"]:.3f} | {stats["recall"]:.3f} | '
                     f'{stats["f1"]:.3f} |')
    lines.extend(['', '## Misclassified cases (incident group, tenant, type, highest score)', ''])
    for label, stats in [('Calibration', cal), ('Held-out test', test)]:
        lines.append(f'**{label}:**')
        if not stats['wrong']:
            lines.append('- None on this small synthetic sample')
        for group, tenant, kind, score in stats['wrong']:
            lines.append(f'- `{group}` / `{tenant}`: {kind.upper()}, similarity={score:.4f}')
    lines.extend(['', '## Limits', '',
                  '- This is a small, hand-written, synthetic sample, not a field accuracy benchmark.',
                  '- Similarity cannot prove that two tickets have the same underlying incident.',
                  '- Duplicate flags only recommend **human review**; tickets are never merged.',
                  '- Additional real-world evaluation and time-based incident grouping are required.'])
    OUTPUT.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'calibration threshold={threshold:.2f}  P={cal["precision"]:.3f} R={cal["recall"]:.3f}')
    print(f'held-out test P={test["precision"]:.3f} R={test["recall"]:.3f} F1={test["f1"]:.3f}')
    print(f'report: {OUTPUT}')


if __name__ == '__main__':
    main()

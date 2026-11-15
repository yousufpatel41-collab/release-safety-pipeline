# Release-safety pipeline

A small Python service whose real purpose is to show how releases get **tested, gated, deployed and rolled back automatically**. The service is a runbook assistant: it answers IT-support questions from a set of *synthetic* runbooks, always cites its source, and refuses when it does not know.

**Status: work in progress.** The code, tests and scripts below exist and run locally. The GitHub Actions pipeline has not run on GitHub yet, and the container build, deploy and rollback scripts have not been run end to end. The results table further down is empty on purpose until they are.

## Why this exists

Many teams already have CI that only builds. This repo is a worked example of adding quality gates in stages instead of all at once, and of treating an AI-style feature (answer from documents, never leak between clients) like production code: tested, access-controlled and logged.

All data in `data/runbooks.json` is invented. No real client, employer or personal data belongs in this repo. Do not expose this demo endpoint to untrusted users or use it with confidential data without adding authentication and authorization.

## What the service does

| Endpoint | Purpose |
|---|---|
| `GET /healthz` | Health check used by the deploy script (returns 503 for a deliberately broken release) |
| `GET /version` | Reports the commit SHA the image was built from |
| `GET /ask?question=...&client=...` | Returns the best matching runbook text and its source id, or "Not found in the runbooks" |

Retrieval is plain BM25 keyword search (no LLM, no API key, no cost). Each runbook chunk carries a `client` tag. The search index restricts retrieval to chunks tagged with the requested client and `shared` ones, and corpus statistics are computed over visible chunks only. **Security limitation:** the demo API accepts `client` as an unauthenticated query parameter, so a caller can impersonate another client. This is a retrieval-isolation demonstration, **not secure production multi-tenancy**. A production implementation must authenticate callers and derive the permitted client ID from a trusted authorization layer. Questions are redacted for e-mail addresses and IBANs before they are logged.

An LLM answer step is a possible next phase. It is not built.

## Pipeline

| Stage | Where | What it checks |
|---|---|---|
| 1. Fast gates | `ci.yml` job `test` | `ruff` lint and format, `pytest` |
| 2. Characterization tests | `tests/test_golden.py` | Pins what the assistant answers today, so changes are deliberate |
| 3. Access-control tests | `tests/test_search.py`, `tests/test_api.py` | One client can never retrieve another client's runbooks |
| 4. Supply-chain checks | `ci.yml` job `test` | `pip-audit` on pinned requirements, `detect-secrets` scan |
| 5. Container smoke test | `ci.yml` job `container-smoke` | Builds the image tagged with the commit SHA, starts it, runs `scripts/smoke_test.sh` |
| 6. Deploy with rollback | `ci.yml` job `deploy` (main only) | `scripts/rollback_drill.sh` deploys a good and a deliberately broken release and asserts the good one is restored, then `scripts/deploy.sh` deploys the real release and smoke-tests it |

`scripts/deploy.sh` runs a health check after deploying. If it fails, it redeploys the previously deployed tag and exits non-zero, so the pipeline goes red. `scripts/check_healthz.sh` exits `0` for OK and `2` for CRITICAL, the plugin convention used by Nagios-style monitors such as Icinga.

To make the pipeline a real gate, turn on branch protection and require the `test` and `container-smoke` checks. To add an approval step before deploying, add required reviewers to the `staging` environment (available on the free plan for public repositories).

## Run it locally

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
ruff check . && ruff format --check . && pytest -q

# with Docker
docker build -t runbook-assistant:dev .
docker compose up -d
scripts/smoke_test.sh
```

## Results of the injected-bug drill

To be filled in after running the pipeline on GitHub. Plan: introduce each bug on a branch, open a pull request, and record which stage caught it.

| Injected bug | Stage that should catch it | Caught by | Evidence |
|---|---|---|---|
| Unused import / formatting error | 1. Fast gates | not yet run | |
| A change that lets one client retrieve another client's chunk | 3. Access-control tests | not yet run | |
| A release whose `/healthz` returns 503 | 6. Deploy with rollback | not yet run | |

## Security notes

- Every third-party GitHub Action is pinned to a full commit SHA (`actions/checkout`, `actions/setup-python`). In March 2026 most tags of a widely used scanner action were hijacked to steal CI secrets, and pinning by SHA is the advised protection. The scanners here are pip-installed instead of using extra actions.
- Runtime dependencies are pinned in `requirements.txt`.
- The container runs as a non-root user.

## Limits and next steps

- One container on one host: no blue-green deploys and no real monitoring stack yet.
- Staging is the ephemeral GitHub runner, so the rollback is exercised there, not on a long-lived server.
- Next: alerting through whatever monitoring a team already has, an optional LLM answer step with a golden-question evaluation, and a persistent deploy target.

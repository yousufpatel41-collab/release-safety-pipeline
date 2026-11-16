# Release-Safety Pipeline — support incident tools and grounded answer selection

[![CI](https://github.com/yousufpatel41-collab/release-safety-pipeline/actions/workflows/ci.yml/badge.svg)](https://github.com/yousufpatel41-collab/release-safety-pipeline/actions/workflows/ci.yml)

A hands-on, synthetic IT-support service demonstrating **secure tenant-aware retrieval**, **small local ML-enhanced search**, **ticket similarity**, **optional source-grounded answer selection**, **Prometheus/Grafana observability**, and **CI/CD quality gates with rollback tests**. Built with FastAPI, Python, Docker and GitHub Actions.

> **Scope:** learning and portfolio demonstration, not a production-hardened multi-tenant platform. No enterprise systems, real client content or financial records are connected. The `deploy` job runs on an ephemeral GitHub runner and does not publish a public service.

## What changed in v2

| Before | Now |
|---|---|
| `GET /ask?client=...` trusted caller-provided tenant | `POST /ask` requires a signed JWT; server obtains the tenant from authenticated user config, not from request body |
| BM25-only search | Hybrid **BM25 + character n-gram TF-IDF** (scikit-learn); robust to some spelling errors; always returns an existing cited runbook |
| Health check / basic logs | Prometheus **HTTP request rate, status codes, latency histograms, login failures, retrieval hit/miss**; Grafana dashboard and alert rules |
| No working demo auth story | Script generates local random JWT signing key, hashed demo password, and metrics bearer token; no secrets in repo |

**AI claim, precisely:** TF-IDF is classical **machine-learning/NLP** retrieval, not a pretrained neural model. An **optional** hosted LLM can select verbatim sentences from one authorized runbook, but it is switched off by default and is not used in CI. The deterministic validator rejects altered facts and unsupported paraphrases. This is **not** a general chatbot or a guarantee against all hallucinations or malicious runbooks.

## Security and data access

- `/auth/token` accepts a JSON username/password; password hashes use salted PBKDF2-HMAC-SHA256 (310,000 rounds).
- `/ask`, `/tickets/similar`, and `/ask/answer` require an `Authorization: Bearer <JWT>` header. Tenant identity is **not** accepted from user input; it comes from the authenticated account.
- Tokens use HS256 with a **random signing key of 32+ bytes**, fixed issuer/audience, mandatory expiry (15 min); revoking or changing a user's account blocks existing tokens. All authentication failures return 401.
- Retrieval is strictly restricted to that tenant's runbooks plus `shared` chunks. Source IDs are returned for evidence; only pre-existing runbook text can be returned.
- Metrics require a separate long random bearer token. Metrics labels deliberately exclude raw questions, usernames, tenant IDs and document text.
- Prometheus/Grafana ports bind to **127.0.0.1** for local demos; never expose to a public network without HTTPS, SSO, secret management and network controls.
- No raw question or bearer token is intentionally recorded by application logs; `POST` avoids query strings in ordinary access logs. Source IDs are logged for operational diagnosis.

**Still missing for production:** OIDC integration, persistent user store and audit trail, rate limiting / lockouts, HTTPS reverse proxy, secrets vault, tenant-level authorization tests on larger data, hardened token lifecycle, backups, and long-lived monitoring/deployment infrastructure.

## Quick start (Windows PowerShell / macOS / Linux)

Use Python 3.13 (or compatible). From the project directory:

```bash
python -m pip install -r requirements-dev.txt
python scripts/generate_demo_env.py
```

Save the **demo password shown once** in the terminal. Then load `.env.demo` into the shell and run:

```bash
# Cross-platform: securely load local .env.demo, then start Uvicorn
python scripts/run_local.py
```

Open `http://127.0.0.1:8000/docs` to see interactive OpenAPI docs. The API is local-only by default in this example.

### Docker + Grafana (recommended cross-platform)

```bash
python scripts/generate_demo_env.py             # only once; do not overwrite credentials
# The script also writes a private .metrics-token for Prometheus

docker build -t runbook-assistant:dev .
docker compose --env-file .env.demo --profile observability up -d
```

Open `http://localhost:8000/docs` for FastAPI, `http://localhost:9090` for Prometheus, `http://localhost:3000` for Grafana (username `admin`, password saved in `.env.demo`).

**Important:** Compose builds only after you run the `docker build` command above. The staging rollout/rollback scripts also use the same `.env.demo` credentials. Images for Prometheus/Grafana have their own upstream supply-chain considerations.

### Example API calls

```bash
# bash example; enter the password you saved from the generator
curl -s -X POST http://localhost:8000/auth/token -H 'Content-Type: application/json' \
  -d '{"username":"demo","password":"<YOUR-GENERATED-PASSWORD>"}'
# Copy access_token from the JSON response
curl -X POST http://localhost:8000/ask -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <ACCESS_TOKEN>' \
  -d '{"question":"VPN will not connect"}'
```

Example: `{"found":true,"answer":"Check the user's internet access first...","source":"shared-002","method":"bm25"}`. `method` may also be `tfidf_char`, depending on which retrieval path is selected.

### Duplicate-ticket suggestions (new)

The API searches **40 invented historical tickets** using a separate character n-gram TF-IDF index for each tenant. The request only supplies the text; the tenant is taken from the authenticated token. It returns up to three earlier ticket IDs with similarity scores and a `possible_duplicate` flag. **This never creates, closes, or merges tickets.** A similar description does not prove the same underlying incident.

```bash
curl -X POST http://localhost:8000/tickets/similar \
  -H 'Content-Type: application/json' -H 'Authorization: Bearer <ACCESS_TOKEN>' \
  -d '{"ticket":"VPN tunnel disconnects every few minutes"}'
```

The threshold **0.40** was chosen on calibration examples and evaluated on an incident-group-disjoint synthetic test set. Measured held-out precision and recall were **1.000 / 1.000** on only **16 hand-written test cases**. This unusually high number is **not** a claim about real-world performance. There was one calibration false positive. See [`docs/duplicates_results.md`](docs/duplicates_results.md) and reproduce with `python -m eval.run_duplicates_eval`.

### Optional model-assisted answer selection (new)

`POST /ask/answer` takes the same JSON payload as `/ask`. Without any configuration it returns the **original retrieved runbook** with `"mode":"extractive"`. If `LLM_ENABLED=1`, it can call an explicitly configured OpenAI-compatible HTTPS chat-completions provider. Provider access also requires `LLM_EXTERNAL_APPROVED=1`, `LLM_API_KEY` and `LLM_MODEL`. **Do not enable external calls for confidential, regulated, or customer data without explicit approval.** Even after redacting email/IBAN patterns, the external model receives the original runbook text and could see other sensitive details.

The model can select **one or two complete, verbatim sentences** from the one authorized source. Every selected sentence needs a valid source tag `[shared-002]`; the validator checks **exact sentence equality**, not word overlap. Any unverified output, provider error or timeout returns the original runbook (`mode=extractive`). This conservative, citation-first approach rejects paraphrases rather than pretending lexical overlap proves a fact. Hostile content patterns trigger a fallback, but **no prompt-injection defense is perfect**.

The offline fake-client evaluation passes **15/15 synthetic examples** and needs no key: `python -m eval.run_answers_eval`. It does **not** evaluate real LLM quality. To explicitly evaluate a real hosted model, use `python -m eval.run_live_answers --execute` with the approval flags configured; this is **not executed in CI**, and no real provider run has been verified for this version. See [`docs/answers_results.md`](docs/answers_results.md).

Example response when enabled and validated:

```json
{"found": true, "answer": "Check the user's internet access first, then confirm the VPN client version. [shared-002]", "source": "shared-002", "mode": "generated"}
```

### Test and release verification

```bash
python -m pytest -q
python -m eval.run_duplicates_eval
python -m eval.run_answers_eval
ruff check .
ruff format --check .
# With Docker installed / .env.demo created:
DEMO_AUTH_VALUE='<YOUR-GENERATED-PASSWORD>' scripts/smoke_test.sh
```

GitHub Actions pipeline stages: ruff → pytest → `pip-audit` → secret scan → Docker build and authenticated smoke test → intentional unhealthy release + automatic rollback drill → ephemeral runner staging. A green run confirms these checks worked, **not** that the application is production-ready or that Grafana was tested end-to-end.

### Prometheus metrics and operational alerts

- `runbook_http_requests_total{method,route,status}` — traffic and failures
- `runbook_http_request_duration_seconds_bucket` — latency histogram / p95
- `runbook_auth_failures_total` — invalid/missing authentication counts
- `runbook_retrieval_total{outcome,method}` — search found/not found counts
- `similar_requests_total{flagged}` — similar-ticket lookups and flags; no tenant or ticket text labels
- `llm_requests_total{mode}` — answer-endpoint outcomes (including disabled/not-found); does not mean an external model was always called
- `llm_check_failures_total` — generated-answer validation or provider failures
- `monitoring/alerts.yml` — example service-down and 5xx-rate alerts (rules are defined; no outbound alert delivery is configured).
- `monitoring/dashboard.json` — 7 charts, automatically provisioned in Grafana.

## Limitations and further work

- The synthetic corpus contains only 12 runbook chunks. Character n-gram TF-IDF sometimes matches the wrong but related runbook; better thresholds, a labeled retrieval evaluation set and optional pretrained embeddings are next.
- The JWT secret and hashed accounts are loaded from demo environment variables; use real identity providers and a secrets manager for any real customers.
- Current CI runner deployment is intentionally temporary. Prometheus/Grafana can be started locally, but production-level alert routing, retention, access controls and persistent deployment are **not** implemented.
- No financial/SAP integration or vector database. The optional hosted LLM is off by default and untested live; avoid describing this project as a production AI agent platform.
- Synthetic threshold scores may be overoptimistic. The duplicate tool has no incident IDs, backend ticket database, or production-grade deduplication decisions.
- The hosted LLM adapter is intentionally minimal; provider API compatibility, reliability, privacy and costs require separate verification before real use.

*Authoring note:* AI-assisted code generation was used as a development aid; tests, documentation, and CI results should be used to validate each claim rather than treating generated code as inherently correct.

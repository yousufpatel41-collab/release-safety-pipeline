# Release-Safety Pipeline v2 — authenticated AI-assisted runbook search

[![CI](https://github.com/yousufpatel41-collab/release-safety-pipeline/actions/workflows/ci.yml/badge.svg)](https://github.com/yousufpatel41-collab/release-safety-pipeline/actions/workflows/ci.yml)

A hands-on, synthetic IT-support service demonstrating **secure tenant-aware retrieval**, **small local ML-enhanced search**, **Prometheus/Grafana observability**, and **CI/CD quality gates with rollback tests**. Built with FastAPI, Python, Docker and GitHub Actions.

> **Scope:** learning and portfolio demonstration, not a production-hardened multi-tenant platform. No enterprise systems, real client content or financial records are connected. The `deploy` job runs on an ephemeral GitHub runner and does not publish a public service.

## What changed in v2

| Before | Now |
|---|---|
| `GET /ask?client=...` trusted caller-provided tenant | `POST /ask` requires a signed JWT; server obtains the tenant from authenticated user config, not from request body |
| BM25-only search | Hybrid **BM25 + character n-gram TF-IDF** (scikit-learn); robust to some spelling errors; always returns an existing cited runbook |
| Health check / basic logs | Prometheus **HTTP request rate, status codes, latency histograms, login failures, retrieval hit/miss**; Grafana dashboard and alert rules |
| No working demo auth story | Script generates local random JWT signing key, hashed demo password, and metrics bearer token; no secrets in repo |

**AI claim, precisely:** TF-IDF is classical **machine-learning/NLP** retrieval, **not a pretrained neural model, LLM, chatbot or generative AI**. No model inference on private data, no paid AI API, no hallucinated generated answers. This intentionally small AI/ML enhancement handles typo-tolerant matching, alongside tested keyword ranking. An optional transformer/LLM would be an independently measured future addition—not part of this version.

## Security and data access

- `/auth/token` accepts a JSON username/password; password hashes use salted PBKDF2-HMAC-SHA256 (310,000 rounds).
- `/ask` accepts `{"question":"VPN will not connect"}` and an `Authorization: Bearer <JWT>` header. Tenant identity is **not** accepted from user input; it comes from the authenticated account.
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
# Linux/macOS only (for Windows see Docker option below)
set -a; . ./.env.demo; set +a
uvicorn app.main:app --reload
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

### Test and release verification

```bash
python -m pytest -q
ruff check .
ruff format --check .
# With Docker installed / .env.demo created:
TEST_DEMO_PASSWORD='<YOUR-GENERATED-PASSWORD>' scripts/smoke_test.sh
```

GitHub Actions pipeline stages: ruff → pytest → `pip-audit` → secret scan → Docker build and authenticated smoke test → intentional unhealthy release + automatic rollback drill → ephemeral runner staging. A green run confirms these checks worked, **not** that the application is production-ready or that Grafana was tested end-to-end.

### Prometheus metrics and operational alerts

- `runbook_http_requests_total{method,route,status}` — traffic and failures
- `runbook_http_request_duration_seconds_bucket` — latency histogram / p95
- `runbook_auth_failures_total` — invalid/missing authentication counts
- `runbook_retrieval_total{outcome,method}` — search found/not found counts
- `monitoring/alerts.yml` — example service-down and 5xx-rate alerts (rules are defined; no outbound alert delivery is configured).
- `monitoring/dashboard.json` — 5 charts, automatically provisioned in Grafana.

## Limitations and further work

- The synthetic corpus contains only 12 runbook chunks. Character n-gram TF-IDF sometimes matches the wrong but related runbook; better thresholds, a labeled retrieval evaluation set and optional pretrained embeddings are next.
- The JWT secret and hashed accounts are loaded from demo environment variables; use real identity providers and a secrets manager for any real customers.
- Current CI runner deployment is intentionally temporary. Prometheus/Grafana can be started locally, but production-level alert routing, retention, access controls and persistent deployment are **not** implemented.
- No financial/SAP integration, no generative AI, no vector database; avoid describing this project as an enterprise agent platform.

*Authoring note:* AI-assisted code generation was used as a development aid; tests, documentation, and CI results should be used to validate each claim rather than treating generated code as inherently correct.

"""Low-cardinality Prometheus observability; no user, question or tenant labels."""

import hmac
import os
import time

from fastapi import HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

HTTP_REQUESTS = Counter(
    "runbook_http_requests_total", "HTTP requests", ["method", "route", "status"]
)
HTTP_DURATION = Histogram(
    "runbook_http_request_duration_seconds",
    "HTTP request duration",
    ["method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
)
RETRIEVAL_TOTAL = Counter("runbook_retrieval_total", "Search outcomes", ["outcome", "method"])
AUTH_FAILURES = Counter("runbook_auth_failures_total", "Authentication failures")
LLM_REQUESTS = Counter("llm_requests_total", "Model answer outcomes", ["mode"])
LLM_CHECK_FAILURES = Counter("llm_check_failures_total", "Failed model answer validations")
SIMILAR_REQUESTS = Counter("similar_requests_total", "Similarity requests", ["flagged"])


async def measure_requests(request: Request, call_next):
    start = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        route = request.scope.get("route")
        # Names from registered endpoints, never paths with arbitrary user input.
        label = route.path if route else "unmatched"
        HTTP_REQUESTS.labels(request.method, label, str(status_code)).inc()
        HTTP_DURATION.labels(request.method, label).observe(time.perf_counter() - start)
        if status_code == 401:
            AUTH_FAILURES.inc()


def metrics_response(request: Request) -> Response:
    expected = os.environ.get("METRICS_TOKEN", "")
    actual = request.headers.get("Authorization", "")
    if len(expected) < 24 or not hmac.compare_digest(actual, f"Bearer {expected}"):
        raise HTTPException(status_code=401, detail="Metrics authentication required")
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

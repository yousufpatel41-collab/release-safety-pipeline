"""Tenant-safe runbook assistant with authentication, ML retrieval and metrics."""

import json
import logging
import os
import re

from fastapi import Depends, FastAPI, Request, Response
from pydantic import BaseModel, Field

from .ai import HybridRetriever
from .auth import LoginRequest, Principal, issue_token, require_user
from .monitoring import RETRIEVAL_TOTAL, measure_requests, metrics_response
from .search import Index, load_chunks

VERSION = os.getenv("APP_VERSION", "dev")
BREAK_HEALTH = os.getenv("BREAK_HEALTH", "0") == "1"

logger = logging.getLogger("runbook")
logging.basicConfig(level=logging.INFO, format="%(message)s")

app = FastAPI(title="Release-Safety Runbook Assistant", version="2.0")
app.middleware("http")(measure_requests)
index = Index(load_chunks())
retriever = HybridRetriever(index)

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){3,7}(?: ?[A-Z0-9]{1,4})?\b")
NOT_FOUND = "Not found in the runbooks. Please contact the IT team."


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=300)


def redact(text: str) -> str:
    return IBAN.sub("[iban]", EMAIL.sub("[email]", text))


@app.get("/healthz")
def healthz(response: Response):
    if BREAK_HEALTH:
        response.status_code = 503
        return {"status": "unhealthy"}
    return {"status": "ok"}


@app.get("/version")
def version():
    return {"version": VERSION}


@app.post("/auth/token")
def token(request: LoginRequest):
    return issue_token(request)


@app.post("/ask")
def ask(request: AskRequest, principal: Principal = Depends(require_user)):
    hit = retriever.search(request.question, principal.tenant)
    method = hit.method if hit else "none"
    RETRIEVAL_TOTAL.labels("found" if hit else "not_found", method).inc()
    # Never log whole raw request, bearer token, tenant or unredacted question.
    logger.info(json.dumps({"event": "ask", "source": hit.chunk.id if hit else None,
                            "method": method}))
    if hit is None:
        return {"found": False, "answer": NOT_FOUND, "source": None, "method": None}
    return {"found": True, "answer": hit.chunk.text, "source": hit.chunk.id,
            "method": hit.method}


@app.get("/metrics")
def metrics(request: Request):
    return metrics_response(request)

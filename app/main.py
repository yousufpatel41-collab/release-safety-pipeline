"""Runbook assistant: answers only from runbooks, always cites a source, otherwise refuses."""

import json
import logging
import os
import re

from fastapi import FastAPI, HTTPException, Query, Response

from .search import SHARED, Index, load_chunks

VERSION = os.getenv("APP_VERSION", "dev")
# Test hook for the rollback drill: a deliberately broken release reports unhealthy.
BREAK_HEALTH = os.getenv("BREAK_HEALTH", "0") == "1"

logger = logging.getLogger("runbook")
logging.basicConfig(level=logging.INFO, format="%(message)s")

app = FastAPI(title="Runbook assistant")
index = Index(load_chunks())

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){3,7}(?: ?[A-Z0-9]{1,4})?\b")
NOT_FOUND = "Not found in the runbooks. Please contact the IT team."


def redact(text: str) -> str:
    """Remove obvious personal data before anything is logged."""
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


@app.get("/ask")
def ask(
    question: str = Query(min_length=3, max_length=300),
    client: str = Query(min_length=1, max_length=50),
):
    if client != SHARED and client not in index.clients():
        raise HTTPException(status_code=404, detail="unknown client")
    hit = index.search(question, client)
    logger.info(
        json.dumps(
            {
                "event": "ask",
                "client": client,
                "question": redact(question),
                "source": hit[0].id if hit else None,
            }
        )
    )
    if hit is None:
        return {"found": False, "answer": NOT_FOUND, "source": None, "client": client}
    chunk, _score = hit
    return {"found": True, "answer": chunk.text, "source": chunk.id, "client": client}

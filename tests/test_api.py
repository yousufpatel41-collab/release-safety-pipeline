import logging

import pytest
from fastapi.testclient import TestClient

from app import main
from app.main import NOT_FOUND, app, redact

client = TestClient(app)


def test_healthz_ok():
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_healthz_unhealthy_when_release_is_broken(monkeypatch):
    monkeypatch.setattr(main, "BREAK_HEALTH", True)
    assert client.get("/healthz").status_code == 503


def test_version_endpoint():
    assert "version" in client.get("/version").json()


def test_answer_cites_a_source():
    r = client.get("/ask", params={"question": "VPN will not connect", "client": "acme"})
    body = r.json()
    assert body["found"] is True
    assert body["source"] == "shared-002"


def test_refuses_out_of_corpus_questions():
    r = client.get("/ask", params={"question": "best pizza topping in Naples", "client": "acme"})
    body = r.json()
    assert body["found"] is False
    assert body["source"] is None
    assert body["answer"] == NOT_FOUND


def test_unknown_client_is_rejected():
    r = client.get("/ask", params={"question": "VPN will not connect", "client": "nobody"})
    assert r.status_code == 404


def test_short_question_is_rejected():
    r = client.get("/ask", params={"question": "hi", "client": "acme"})
    assert r.status_code == 422


@pytest.mark.parametrize(
    "question",
    [
        "Globex negotiation workspace access",
        "Globex pricing model files restricted share",
    ],
)
def test_no_cross_client_leak(question):
    r = client.get("/ask", params={"question": question, "client": "acme"})
    body = r.json()
    assert body["source"] is None or not body["source"].startswith("globex")
    assert "Globex" not in body["answer"]


def test_redact_removes_email_and_iban():
    text = "mail anna@example.com about DE89 3704 0044 0532 0130 00"
    assert redact(text) == "mail [email] about [iban]"


def test_logs_do_not_contain_personal_data(caplog):
    with caplog.at_level(logging.INFO, logger="runbook"):
        client.get(
            "/ask",
            params={"question": "reset password for anna@example.com", "client": "acme"},
        )
    assert "anna@example.com" not in caplog.text

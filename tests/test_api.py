import json
import logging
import os

import jwt
import pytest

from app import main
from app.auth import hash_password, verify_password
from app.main import NOT_FOUND, redact


def test_healthz_ok(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_healthz_unhealthy_when_release_is_broken(client, monkeypatch):
    monkeypatch.setattr(main, "BREAK_HEALTH", True)
    assert client.get("/healthz").status_code == 503


def test_version_endpoint(client):
    assert "version" in client.get("/version").json()


def test_answer_cites_a_source(client, acme_auth):
    r = client.post("/ask", json={"question": "VPN will not connect"}, headers=acme_auth)
    assert r.status_code == 200
    assert r.json()["found"] is True
    assert r.json()["source"] == "shared-002"
    assert r.json()["method"] in ("bm25", "tfidf_char")


def test_refuses_out_of_corpus_questions(client, acme_auth):
    body = client.post("/ask", json={"question": "best pizza topping in Naples"}, headers=acme_auth).json()
    assert body["found"] is False
    assert body["answer"] == NOT_FOUND
    assert body["source"] is None


def test_no_access_without_token(client):
    assert client.post("/ask", json={"question": "VPN will not connect"}).status_code == 401


def test_bogus_token_rejected(client):
    assert client.post("/ask", json={"question": "VPN will not connect"},
                       headers={"Authorization": "Bearer forged.token.signature"}).status_code == 401


def test_invalid_password_rejected(client):
    response = client.post("/auth/token", json={"username": "alice", "password": "bad"})
    assert response.status_code == 401


def test_unknown_user_rejected(client):
    assert client.post("/auth/token", json={"username": "notreal", "password": "bad"}).status_code == 401


def test_expired_token_rejected(client, monkeypatch):
    # Invalid exp even with a valid signature.
    token = jwt.encode({"sub": "alice", "tenant": "acme", "iss": "release-safety-runbook",
                        "aud": "runbook-api", "exp": 1}, os.environ["AUTH_JWT_SECRET"],
                       algorithm="HS256")
    r = client.post("/ask", json={"question": "VPN will not connect"},
                    headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_token_tenant_claim_cannot_be_forged(client, acme_auth):
    original = acme_auth["Authorization"].split()[1]
    header, payload, signature = original.split(".")
    # Substituting the audience/tenant invalidates the signature.
    r = client.post("/ask", json={"question": "Globex pricing model"},
                    headers={"Authorization": f"Bearer {header}.{payload[:-1]}A.{signature}"})
    assert r.status_code == 401


def test_cross_tenant_runbooks_not_accessible(client, acme_auth, globex_auth):
    query = {"question": "Globex negotiation workspace access"}
    acme = client.post("/ask", json=query, headers=acme_auth)
    globex = client.post("/ask", json=query, headers=globex_auth)
    assert acme.status_code == globex.status_code == 200
    assert acme.json()["source"] != "globex-001"
    assert globex.json()["source"] == "globex-001"
    assert "Globex" not in acme.json()["answer"]


def test_cannot_choose_client_in_request_body(client, acme_auth):
    r = client.post("/ask", json={"question": "Globex pricing model files", "client": "globex"},
                    headers=acme_auth)
    assert r.status_code == 200
    assert r.json()["source"] != "globex-002"


def test_short_question_rejected(client, acme_auth):
    r = client.post("/ask", json={"question": "hi"}, headers=acme_auth)
    assert r.status_code == 422


def test_get_ask_not_supported(client):
    assert client.get("/ask", params={"client": "globex", "question": "Globex pricing"}).status_code == 405


def test_password_hash_uses_salt():
    a = hash_password("pass")
    b = hash_password("pass")
    assert a != b and verify_password("pass", a)
    assert not verify_password("incorrect", b)


def test_redact_removes_email_and_iban():
    assert redact("mail anna@example.com about DE89 3704 0044 0532 0130 00") == "mail [email] about [iban]"


def test_logs_do_not_contain_personal_data(client, acme_auth, caplog):
    with caplog.at_level(logging.INFO, logger="runbook"):
        client.post("/ask", json={"question": "reset password for anna@example.com"}, headers=acme_auth)
    assert "anna@example.com" not in caplog.text
    assert "Bearer" not in caplog.text


def test_metrics_requires_token(client):
    assert client.get("/metrics").status_code == 401
    assert client.get("/metrics", headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_metrics_expose_prometheus_counters(client, acme_auth, monkeypatch):
    client.post("/ask", json={"question": "VPN will not connect"}, headers=acme_auth)
    import os
    r = client.get("/metrics", headers={"Authorization": f"Bearer {os.environ['METRICS_TOKEN']}"})
    assert r.status_code == 200
    assert "runbook_http_requests_total" in r.text
    assert "runbook_http_request_duration_seconds" in r.text
    assert "runbook_retrieval_total" in r.text
    assert "alice" not in r.text
    assert "acme" not in r.text


def test_user_revoke_blocks_existing_token(client, acme_auth, monkeypatch):
    monkeypatch.setenv("RUNBOOK_USERS_JSON", json.dumps({}))
    r = client.post("/ask", json={"question": "VPN will not connect"}, headers=acme_auth)
    assert r.status_code == 401

import json
import secrets

import pytest
from fastapi.testclient import TestClient

from app.auth import hash_password
from app.main import app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("AUTH_JWT_SECRET", secrets.token_urlsafe(48))
    monkeypatch.setenv("METRICS_TOKEN", secrets.token_urlsafe(32))
    monkeypatch.setenv(
        "RUNBOOK_USERS_JSON",
        json.dumps(
            {
                "alice": {"tenant": "acme", "password_hash": hash_password("alice-pass")},
                "bob": {"tenant": "globex", "password_hash": hash_password("bob-pass")},
            }
        ),
    )
    return TestClient(app)


@pytest.fixture
def acme_auth(client):
    response = client.post("/auth/token", json={"username": "alice", "password": "alice-pass"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def globex_auth(client):
    response = client.post("/auth/token", json={"username": "bob", "password": "bob-pass"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}

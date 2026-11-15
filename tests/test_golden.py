"""Stable source grounding: any model/ranking change must preserve intended answers."""

import pytest

GOLDEN = [
    ("acme", "alice", "alice-pass", "I forgot my password", "shared-001"),
    ("acme", "alice", "alice-pass", "VPN will not connect", "shared-002"),
    ("acme", "alice", "alice-pass", "linux server disk is almost full", "shared-003"),
    ("acme", "alice", "alice-pass", "certificate is about to expire", "shared-004"),
    ("acme", "alice", "alice-pass", "who approves Acme project room access", "acme-001"),
    ("globex", "bob", "bob-pass", "who approves Globex negotiation workspace access", "globex-001"),
    ("globex", "bob", "bob-pass", "monthly patch window", "shared-008"),
]


@pytest.mark.parametrize(("tenant", "user", "password", "question", "expected"), GOLDEN)
def test_golden_answers(client, tenant, user, password, question, expected):
    token = client.post("/auth/token", json={"username": user, "password": password}).json()["access_token"]
    r = client.post("/ask", json={"question": question}, headers={"Authorization": f"Bearer {token}"})
    assert r.json()["source"] == expected

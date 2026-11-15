"""Characterization (snapshot) tests: pin what the assistant answers today.

If one of these changes, a person must decide whether the new behaviour is better.
Update the expected source ids deliberately, never to make a red build green.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

GOLDEN = [
    ("acme", "I forgot my password", "shared-001"),
    ("acme", "VPN will not connect", "shared-002"),
    ("acme", "linux server disk is almost full", "shared-003"),
    ("acme", "certificate is about to expire", "shared-004"),
    ("acme", "who approves Acme project room access", "acme-001"),
    ("globex", "who approves Globex negotiation workspace access", "globex-001"),
    ("globex", "monthly patch window", "shared-008"),
]


@pytest.mark.parametrize(("who", "question", "expected"), GOLDEN)
def test_golden_answers(who, question, expected):
    r = client.get("/ask", params={"question": question, "client": who})
    assert r.json()["source"] == expected

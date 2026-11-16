"""Client boundary, similarity behavior, and honest synthetic evaluation tests."""

import json
import logging
from pathlib import Path

from app.duplicates import DUPLICATE_THRESHOLD, DuplicateFinder, Ticket, load_tickets
from eval.run_duplicates_eval import run


def test_ticket_file_has_only_synthetic_sample():
    history = load_tickets()
    assert len(history) == 40
    assert {ticket.tenant for ticket in history} == {"acme", "globex"}
    assert len({ticket.ticket_id for ticket in history}) == len(history)


def test_similarity_requires_authentication(client):
    assert client.post("/tickets/similar", json={"ticket": "VPN drops often"}).status_code == 401


def test_similarity_has_max_three_results(client, acme_auth):
    response = client.post(
        "/tickets/similar", json={"ticket": "VPN drops every few minutes"}, headers=acme_auth
    )
    assert response.status_code == 200
    body = response.json()
    assert body["possible_duplicate"] is True
    assert 1 <= len(body["matches"]) <= 3
    assert body["matches"][0]["ticket_id"] in {"A-101", "A-102"}
    assert 0 <= body["matches"][0]["score"] <= 1


def test_unrelated_ticket_not_flagged(client, acme_auth):
    response = client.post(
        "/tickets/similar", json={"ticket": "New contractor travel reimbursement policy"},
        headers=acme_auth,
    )
    assert response.status_code == 200
    assert response.json()["possible_duplicate"] is False


def test_tenant_never_receives_other_tenant_ticket_ids(client, acme_auth, globex_auth):
    item = {"ticket": "Invoice transfer to SAP ERP returns gateway timeout 504"}
    acme = client.post("/tickets/similar", json=item, headers=acme_auth)
    globex = client.post("/tickets/similar", json=item, headers=globex_auth)
    assert acme.status_code == globex.status_code == 200
    assert all(m["ticket_id"].startswith("A-") for m in acme.json()["matches"])
    assert any(m["ticket_id"].startswith("G-") for m in globex.json()["matches"])


def test_tenant_override_in_body_is_ignored(client, acme_auth):
    response = client.post(
        "/tickets/similar",
        json={"ticket": "Invoice transfer to SAP ERP returns gateway timeout", "tenant": "globex"},
        headers=acme_auth,
    )
    assert response.status_code == 200
    assert all(m["ticket_id"].startswith("A-") for m in response.json()["matches"])


def test_ticket_body_never_appears_in_application_logs(client, acme_auth, caplog):
    phrase = "unique support request text ABC2346"
    with caplog.at_level(logging.INFO, logger="runbook"):
        client.post("/tickets/similar", json={"ticket": phrase}, headers=acme_auth)
    assert phrase not in caplog.text
    assert "Authorization" not in caplog.text


def test_empty_history_returns_empty_results():
    finder = DuplicateFinder([])
    assert finder.find("VPN tunnel drops frequently", "acme") == {
        "matches": [], "possible_duplicate": False
    }


def test_other_tenant_text_does_not_enter_tfidf_index():
    finder = DuplicateFinder([
        Ticket("A-1", "acme", "printer offline", "2026-01-01"),
        Ticket("G-1", "globex", "invoice gateway timeout", "2026-01-01"),
    ])
    assert finder.find("invoice gateway timeout", "acme")["possible_duplicate"] is False


def test_similarity_deterministic_and_sorted():
    finder = DuplicateFinder(load_tickets())
    one = finder.find("VPN drops every few minutes", "acme")
    two = finder.find("VPN drops every few minutes", "acme")
    assert one == two
    assert [x["score"] for x in one["matches"]] == sorted(
        [x["score"] for x in one["matches"]], reverse=True
    )


def test_calibration_and_heldout_groups_are_disjoint():
    data = json.loads((Path(__file__).resolve().parent.parent / "eval/duplicates.json").read_text())
    dev = {q["incident_group"] for q in data["calibration"]}
    test = {q["incident_group"] for q in data["test"]}
    assert dev.isdisjoint(test)
    threshold, calibration, heldout = run()
    assert threshold == DUPLICATE_THRESHOLD
    assert calibration["precision"] >= 0.70
    assert heldout["precision"] >= 0.70
    assert heldout["recall"] >= 0.70


def test_malformed_short_ticket_returns_422(client, acme_auth):
    assert client.post("/tickets/similar", json={"ticket": ""}, headers=acme_auth).status_code == 422

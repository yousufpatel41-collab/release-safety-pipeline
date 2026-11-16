"""Deterministic, tenant-scoped candidate search for possible duplicate incidents.

This is a decision aid. It never merges or changes a ticket. Similar wording
alone cannot establish that two customer reports share a root cause.
"""

import csv
from dataclasses import dataclass
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

TICKETS_CSV = Path(__file__).resolve().parent.parent / "data" / "ticket_history.csv"
# Selected on the calibration examples only. See docs/duplicates_results.md.
DUPLICATE_THRESHOLD = 0.40


@dataclass(frozen=True)
class Ticket:
    ticket_id: str
    tenant: str
    text: str
    created: str


def load_tickets(path: Path = TICKETS_CSV) -> list[Ticket]:
    with path.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        expected = {"ticket_id", "tenant", "text", "created"}
        if not expected.issubset(reader.fieldnames or []):
            raise ValueError("Ticket history is missing required columns")
        tickets = [Ticket(**{key: row[key] for key in expected}) for row in reader]
    ids = [ticket.ticket_id for ticket in tickets]
    if len(ids) != len(set(ids)):
        raise ValueError("Ticket IDs must be unique")
    return tickets


class DuplicateFinder:
    """One TF-IDF index per tenant; no mixed-tenant vocabulary or features."""

    def __init__(self, tickets: list[Ticket], threshold: float = DUPLICATE_THRESHOLD):
        if not 0 <= threshold <= 1:
            raise ValueError("Duplicate threshold must be between zero and one")
        self.threshold = threshold
        self._tenants: dict[str, tuple[list[Ticket], TfidfVectorizer, object]] = {}
        for tenant in sorted({ticket.tenant for ticket in tickets}):
            visible = [ticket for ticket in tickets if ticket.tenant == tenant and ticket.text.strip()]
            if not visible:
                continue
            vectorizer = TfidfVectorizer(
                analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True
            )
            matrix = vectorizer.fit_transform([ticket.text for ticket in visible])
            self._tenants[tenant] = (visible, vectorizer, matrix)

    def find(self, ticket_text: str, tenant: str, limit: int = 3) -> dict:
        entry = self._tenants.get(tenant)
        if not entry or not ticket_text.strip():
            return {"matches": [], "possible_duplicate": False}
        tickets, vectorizer, matrix = entry
        similarities = cosine_similarity(vectorizer.transform([ticket_text]), matrix)[0]
        # Stable ordering for equal scores makes tests reproducible.
        ranked = sorted(range(len(tickets)), key=lambda pos: (-similarities[pos], tickets[pos].ticket_id))
        matches = [
            {"ticket_id": tickets[i].ticket_id, "score": round(float(similarities[i]), 4)}
            for i in ranked[:limit]
            if similarities[i] > 0
        ]
        top_score = float(similarities[ranked[0]]) if ranked else 0.0
        return {"matches": matches, "possible_duplicate": top_score >= self.threshold}

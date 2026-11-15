"""Tiny BM25 keyword search over runbook chunks with per-client visibility.

Isolation lives here, in retrieval: a client can only ever score chunks tagged with its own
name or "shared". Corpus statistics are computed over the visible chunks only, so nothing about
other clients' documents leaks through scores either.
"""

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "runbooks.json"
TOKEN = re.compile(r"[a-z0-9]+")
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "for", "from", "how", "i",
    "in", "is", "it", "of", "on", "or", "the", "to", "what", "when", "which", "with", "my",
    "we", "our", "does", "should", "if", "you",
}  # fmt: skip
SHARED = "shared"
K1 = 1.5
B = 0.75
MIN_SCORE = 2.0


@dataclass(frozen=True)
class Chunk:
    id: str
    client: str
    title: str
    text: str


def tokenize(text: str) -> list[str]:
    return [t for t in TOKEN.findall(text.lower()) if t not in STOPWORDS and len(t) > 1]


def load_chunks(path: Path = DATA_FILE) -> list[Chunk]:
    with open(path, encoding="utf-8") as fh:
        return [Chunk(**item) for item in json.load(fh)]


class Index:
    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks

    def clients(self) -> set[str]:
        return {c.client for c in self.chunks if c.client != SHARED}

    def visible(self, client: str) -> list[Chunk]:
        return [c for c in self.chunks if c.client in (client, SHARED)]

    def search(self, question: str, client: str) -> tuple[Chunk, float] | None:
        """Return the best visible chunk for the question, or None if nothing scores well."""
        docs = self.visible(client)
        query = set(tokenize(question))
        if not docs or not query:
            return None
        tokenized = [Counter(tokenize(f"{d.title} {d.text}")) for d in docs]
        lengths = [sum(tf.values()) for tf in tokenized]
        avg_len = sum(lengths) / len(lengths)
        n_docs = len(docs)

        best: tuple[Chunk, float] | None = None
        for doc, tf, length in zip(docs, tokenized, lengths, strict=True):
            score = 0.0
            for term in query:
                freq = tf.get(term, 0)
                if not freq:
                    continue
                n_with = sum(1 for other in tokenized if term in other)
                idf = math.log(1 + (n_docs - n_with + 0.5) / (n_with + 0.5))
                score += idf * freq * (K1 + 1) / (freq + K1 * (1 - B + B * length / avg_len))
            if best is None or score > best[1]:
                best = (doc, score)
        if best is None or best[1] < MIN_SCORE:
            return None
        return best

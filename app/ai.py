"""Tiny, deterministic local ML retriever: character n-gram TF-IDF + BM25.

This is classical ML / information retrieval, *not* an LLM and not a semantic
transformer. The hybrid improves tolerance to typos and terminology variations.
It only scores documents already authorized by tenant filtering.
"""

from dataclasses import dataclass

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .search import MIN_SCORE, Chunk, Index, tokenize


@dataclass(frozen=True)
class Retrieval:
    chunk: Chunk
    method: str
    score: float


class HybridRetriever:
    def __init__(self, index: Index):
        self.index = index
        self.vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)
        self._all = index.chunks
        self._embeddings = self.vectorizer.fit_transform(
            [f"{c.title} {c.text}" for c in self._all]
        )

    def search(self, question: str, tenant: str) -> Retrieval | None:
        allowed = [(i, c) for i, c in enumerate(self._all) if c.client in (tenant, "shared")]
        if not allowed or not tokenize(question):
            return None
        baseline = self.index.search(question, tenant)
        ids = [i for i, _ in allowed]
        similarities = cosine_similarity(
            self.vectorizer.transform([question]), self._embeddings[ids]
        )[0]
        best_idx = int(similarities.argmax())
        candidate = allowed[best_idx][1]
        candidate_score = float(similarities[best_idx])

        # Conservative: only trust ML-only matches with relatively high cosine
        # similarity; otherwise keep the tested BM25 ground-truth behavior.
        if baseline and candidate_score < 0.36:
            return Retrieval(baseline[0], "bm25", baseline[1])
        if candidate_score >= 0.44:
            return Retrieval(candidate, "tfidf_char", candidate_score)
        if baseline and baseline[1] >= MIN_SCORE:
            return Retrieval(baseline[0], "bm25", baseline[1])
        return None

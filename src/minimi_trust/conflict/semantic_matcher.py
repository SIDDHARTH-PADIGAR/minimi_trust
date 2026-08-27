"""
Semantic Candidate Matcher (M3, §7).

Broadens conflict-candidate generation beyond exact subject+predicate
string matching, using TF-IDF cosine similarity over (subject, predicate)
key text. This is a lexical/statistical similarity proxy, NOT a true
dense embedding — it catches shared-token near-duplicates (e.g.
"jordan_current_role" vs "jordan_role_title") but will NOT catch pure
synonym rewrites with no shared vocabulary (e.g. "role" vs "job title").
That gap is real and expected; closing it needs a real embedding model
or LLM judgment, neither in scope here.

Resolution among matched candidates still runs through the exact same
deterministic logic as M2 (ConflictDetector.resolve_facts) — M3 only
changes WHICH facts are considered, never HOW the winner is picked.
"""

from __future__ import annotations

from dataclasses import dataclass

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from minimi_trust.store.fact_store import FactStore

DEFAULT_SIMILARITY_THRESHOLD = 0.3


def _key_text(subject: str, predicate: str) -> str:
    return f"{subject} {predicate}".replace("_", " ")


@dataclass
class CandidateKey:
    subject: str
    predicate: str
    similarity: float


class SemanticCandidateMatcher:
    def __init__(self, store: FactStore, threshold: float = DEFAULT_SIMILARITY_THRESHOLD):
        self.store = store
        self.threshold = threshold

    def find_candidate_keys(self, subject: str, predicate: str) -> list[CandidateKey]:
        """Returns OTHER (subject, predicate) keys in the store whose key
        text is similar enough to be treated as candidates for the same
        conflict — excludes the exact query key itself."""
        all_keys = self.store.get_distinct_subject_predicate_pairs()
        query_key = (subject, predicate)
        other_keys = [k for k in all_keys if k != query_key]

        if not other_keys:
            return []

        corpus = [_key_text(subject, predicate)] + [_key_text(s, p) for s, p in other_keys]
        vectorizer = TfidfVectorizer()
        try:
            matrix = vectorizer.fit_transform(corpus)
        except ValueError:
            # corpus was all-empty/stopword-only — nothing to match on
            return []

        similarities = cosine_similarity(matrix[0:1], matrix[1:]).flatten()

        candidates = [
            CandidateKey(subject=s, predicate=p, similarity=float(sim))
            for (s, p), sim in zip(other_keys, similarities)
            if sim >= self.threshold
        ]
        return sorted(candidates, key=lambda c: c.similarity, reverse=True)
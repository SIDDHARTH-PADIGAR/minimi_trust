"""
Recall Plane — minimal retrieval + Explain layer (M6, §2/§4 explain_retrieval).

Deliberately small: TF-IDF search over currently-active facts' text,
annotated with provenance, confidence, a staleness heuristic, and
whether the fact currently has an unresolved conflict at its
(subject, predicate) key. Per §8, the scope is "make retrieval honest,"
not "build a real search engine."
"""

from __future__ import annotations

from datetime import datetime, timezone

from minimi_trust.schemas import Fact, FactStatus
from minimi_trust.store.fact_store import FactStore
from minimi_trust.textsim import tfidf_cosine_similarities

# Heuristic threshold, not a measured value — a fact not reconfirmed in
# this many days is flagged as possibly stale for the reader to judge.
STALENESS_THRESHOLD_DAYS = 180


def _fact_text(fact: Fact) -> str:
    parts = [fact.subject.replace("_", " "), fact.predicate.replace("_", " "), fact.object.replace("_", " ")]
    if fact.raw_text:
        parts.append(fact.raw_text)
    return " ".join(parts)


class RecallIndex:
    def __init__(self, store: FactStore):
        self.store = store

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        active_facts = self.store.get_all_active_facts()
        if not active_facts:
            return []

        doc_texts = [_fact_text(f) for f in active_facts]
        similarities = tfidf_cosine_similarities(query, doc_texts)
        ranked = sorted(zip(active_facts, similarities), key=lambda pair: pair[1], reverse=True)

        results = []
        now = datetime.now(timezone.utc)
        for fact, similarity in ranked[:top_k]:
            if similarity <= 0:
                continue
            staleness_days = (now - fact.observed_at).days
            sibling_active = [
                f for f in self.store.get_facts(fact.subject, fact.predicate) if f.status == FactStatus.ACTIVE
            ]
            results.append({
                "fact_id": fact.id, "subject": fact.subject, "predicate": fact.predicate, "object": fact.object,
                "similarity": float(similarity),
                "provenance": {
                    "source_document_id": fact.source_document_id, "observed_at": fact.observed_at.isoformat(),
                },
                "confidence": fact.confidence,
                "staleness_days": staleness_days,
                "possibly_stale": staleness_days > STALENESS_THRESHOLD_DAYS,
                "has_unresolved_conflict": len(sibling_active) > 1,
            })
        return results
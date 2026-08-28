"""
Semantic-candidate-aware Conflict Detector (M3).

Wraps SemanticCandidateMatcher + the M2 ConflictDetector: broadens which
facts are pulled into a resolution via TF-IDF similarity over
(subject, predicate) keys, then hands the merged fact set to the exact
same deterministic resolution logic as M2. No new resolution rules —
only a wider candidate set.

M7: the full body (candidate matching + merge + resolve) is held under
store.operation_lock — otherwise the store could change between finding
candidates and resolving them, even though resolve_facts() itself is
also locked. RLock makes the nested reentry into resolve_facts safe.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from minimi_trust.conflict.detector import ConflictDetector, ConflictResolution
from minimi_trust.conflict.semantic_matcher import (
    DEFAULT_SIMILARITY_THRESHOLD,
    CandidateKey,
    SemanticCandidateMatcher,
)
from minimi_trust.store.fact_store import FactStore


@dataclass
class SemanticConflictResolution(ConflictResolution):
    matched_candidate_keys: list[CandidateKey] = field(default_factory=list)


class SemanticConflictDetector:
    def __init__(self, store: FactStore, similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD):
        self.store = store
        self.matcher = SemanticCandidateMatcher(store, threshold=similarity_threshold)
        self.base_detector = ConflictDetector(store)

    def resolve_conflict(self, subject: str, predicate: str) -> SemanticConflictResolution:
        with self.store.operation_lock:
            candidates = self.matcher.find_candidate_keys(subject, predicate)

            merged_facts = list(self.store.get_facts(subject, predicate))
            for c in candidates:
                merged_facts.extend(self.store.get_facts(c.subject, c.predicate))

            base_result = self.base_detector.resolve_facts(subject, predicate, merged_facts)

            return SemanticConflictResolution(
                subject=base_result.subject, predicate=base_result.predicate,
                winning_fact=base_result.winning_fact, resolution_method=base_result.resolution_method,
                unresolved=base_result.unresolved, version_history=base_result.version_history,
                newly_superseded_ids=base_result.newly_superseded_ids, reason=base_result.reason,
                matched_candidate_keys=candidates,
            )
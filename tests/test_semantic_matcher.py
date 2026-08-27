"""
M3 unit tests for TF-IDF-based semantic candidate matching, independent
of the eval harness.
"""

from datetime import datetime, timezone

from minimi_trust.conflict.semantic_detector import SemanticConflictDetector
from minimi_trust.conflict.semantic_matcher import SemanticCandidateMatcher
from minimi_trust.schemas import Fact
from minimi_trust.store.fact_store import FactStore


def _fact(subject, predicate, object_, observed_at, source="src_test", confidence=0.9):
    return Fact(
        subject=subject, predicate=predicate, object=object_,
        source_document_id=source, observed_at=observed_at, extracted_at=observed_at,
        confidence=confidence,
    )


def test_finds_lexically_similar_candidate_key():
    with FactStore(":memory:") as store:
        store.add_fact(_fact("jordan_current_role", "is", "engineering_manager", datetime(2026, 1, 1, tzinfo=timezone.utc)))
        store.add_fact(_fact("jordan_role_title", "is", "director_of_engineering", datetime(2026, 6, 1, tzinfo=timezone.utc)))
        matcher = SemanticCandidateMatcher(store)
        candidates = matcher.find_candidate_keys("jordan_current_role", "is")
        assert any(c.subject == "jordan_role_title" for c in candidates)


def test_does_not_match_unrelated_keys():
    with FactStore(":memory:") as store:
        store.add_fact(_fact("office_wifi_password", "is", "hunter2", datetime(2026, 1, 1, tzinfo=timezone.utc)))
        store.add_fact(_fact("parking_garage_code", "is", "4471", datetime(2026, 1, 1, tzinfo=timezone.utc)))
        matcher = SemanticCandidateMatcher(store)
        candidates = matcher.find_candidate_keys("office_wifi_password", "is")
        assert candidates == []


def test_semantic_detector_merges_and_resolves_across_matched_keys():
    with FactStore(":memory:") as store:
        store.add_fact(_fact("jordan_current_role", "is", "engineering_manager", datetime(2026, 1, 1, tzinfo=timezone.utc)))
        store.add_fact(_fact("jordan_role_title", "is", "director_of_engineering", datetime(2026, 6, 1, tzinfo=timezone.utc)))
        result = SemanticConflictDetector(store).resolve_conflict("jordan_current_role", "is")
        assert not result.unresolved
        assert result.winning_fact.object == "director_of_engineering"
        assert len(result.matched_candidate_keys) == 1


def test_semantic_detector_reduces_to_m2_when_no_candidates_exist():
    """With only one (subject, predicate) key in the store, semantic
    matching has nothing to find — behavior must be identical to M2."""
    with FactStore(":memory:") as store:
        store.add_fact(_fact("x", "is", "y", datetime(2026, 1, 1, tzinfo=timezone.utc)))
        result = SemanticConflictDetector(store).resolve_conflict("x", "is")
        assert not result.unresolved
        assert result.winning_fact.object == "y"
        assert result.matched_candidate_keys == []
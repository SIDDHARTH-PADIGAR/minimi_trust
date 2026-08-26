"""
M2 unit tests for the deterministic Conflict Detector, independent of the
eval harness — these test the FactStore + ConflictDetector directly
against the actual public contract (resolve_conflict semantics, §4).
"""

from datetime import datetime, timezone

from minimi_trust.conflict.detector import ConflictDetector
from minimi_trust.schemas import Fact, FactStatus, ResolutionMethod
from minimi_trust.store.fact_store import FactStore


def _fact(subject, predicate, object_, observed_at, source="src_test", confidence=0.9):
    return Fact(
        subject=subject, predicate=predicate, object=object_,
        source_document_id=source, observed_at=observed_at, extracted_at=observed_at,
        confidence=confidence,
    )


def test_single_active_fact_is_trivially_resolved():
    with FactStore(":memory:") as store:
        store.add_fact(_fact("x", "is", "y", datetime(2026, 1, 1, tzinfo=timezone.utc)))
        result = ConflictDetector(store).resolve_conflict("x", "is")
        assert not result.unresolved
        assert result.winning_fact.object == "y"
        assert result.resolution_method == ResolutionMethod.DETERMINISTIC


def test_redundant_observations_consolidate_without_conflict():
    with FactStore(":memory:") as store:
        store.add_fact(_fact("x", "is", "y", datetime(2026, 1, 1, tzinfo=timezone.utc)))
        store.add_fact(_fact("x", "is", "y", datetime(2026, 2, 1, tzinfo=timezone.utc)))
        result = ConflictDetector(store).resolve_conflict("x", "is")
        assert not result.unresolved
        assert result.winning_fact.object == "y"
        assert len(result.newly_superseded_ids) == 1
        remaining = store.get_facts("x", "is")
        statuses = {f.status for f in remaining}
        assert FactStatus.SUPERSEDED in statuses
        assert len(remaining) == 2  # older duplicate is marked superseded, not deleted


def test_newest_observed_at_wins_and_writes_supersession_event():
    with FactStore(":memory:") as store:
        store.add_fact(_fact("x", "is", "old", datetime(2026, 1, 1, tzinfo=timezone.utc)))
        store.add_fact(_fact("x", "is", "new", datetime(2026, 2, 1, tzinfo=timezone.utc)))
        result = ConflictDetector(store).resolve_conflict("x", "is")
        assert not result.unresolved
        assert result.winning_fact.object == "new"
        events = store.get_events("supersession")
        assert len(events) == 1
        assert events[0]["payload"]["winning_fact_id"] == result.winning_fact.id


def test_same_timestamp_different_objects_is_unresolved_not_guessed():
    ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with FactStore(":memory:") as store:
        store.add_fact(_fact("x", "is", "a", ts))
        store.add_fact(_fact("x", "is", "b", ts))
        result = ConflictDetector(store).resolve_conflict("x", "is")
        assert result.unresolved
        assert result.winning_fact is None
        assert store.get_events("supersession") == []  # no forced guess is ever written


def test_no_facts_found_is_unresolved():
    with FactStore(":memory:") as store:
        result = ConflictDetector(store).resolve_conflict("nonexistent", "is")
        assert result.unresolved
        assert result.winning_fact is None
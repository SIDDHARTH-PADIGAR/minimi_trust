"""
Deterministic Conflict Detector (M2, §2 Control Plane).

Timestamp/versioning logic, subject+predicate exact matching. No
embeddings, no semantic candidate matching (M3), no LLM arbitration (M4).

Differences from baseline 3 (pure_deterministic_resolver in eval/baselines.py):
same-object "conflicts" (redundant re-observations) are recognized as
non-conflicts rather than arbitrarily re-picked, and genuine same-timestamp
conflicts between DIFFERENT objects are reported unresolved rather than
forced to a guess. Every real resolution is written to the Fact Store as
a supersession — losing facts are marked superseded, never deleted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from minimi_trust.schemas import Fact, FactStatus, ResolutionMethod
from minimi_trust.store.fact_store import FactStore


@dataclass
class ConflictResolution:
    subject: str
    predicate: str
    winning_fact: Optional[Fact]
    resolution_method: ResolutionMethod
    unresolved: bool
    version_history: list[Fact] = field(default_factory=list)
    newly_superseded_ids: list[str] = field(default_factory=list)
    reason: str = ""


class ConflictDetector:
    def __init__(self, store: FactStore):
        self.store = store

    def resolve_conflict(self, subject: str, predicate: str) -> ConflictResolution:
        all_facts = self.store.get_facts(subject, predicate)
        active = [f for f in all_facts if f.status == FactStatus.ACTIVE]

        if not active:
            return ConflictResolution(
                subject=subject, predicate=predicate, winning_fact=None,
                resolution_method=ResolutionMethod.UNRESOLVED, unresolved=True,
                version_history=all_facts, reason="no active facts found for subject+predicate",
            )

        if len(active) == 1:
            return ConflictResolution(
                subject=subject, predicate=predicate, winning_fact=active[0],
                resolution_method=ResolutionMethod.DETERMINISTIC, unresolved=False,
                version_history=all_facts, reason="single active fact, no contention",
            )

        distinct_objects = {f.object for f in active}

        if len(distinct_objects) == 1:
            # Redundant re-observations, not a real conflict.
            winner = max(active, key=lambda f: (f.observed_at, f.extracted_at, f.id))
            losers = [f for f in active if f.id != winner.id]
            self._consolidate(subject, predicate, winner, losers, reason="redundant_consolidation")
            return ConflictResolution(
                subject=subject, predicate=predicate, winning_fact=winner,
                resolution_method=ResolutionMethod.DETERMINISTIC, unresolved=False,
                version_history=all_facts, newly_superseded_ids=[loser.id for loser in losers],
                reason="identical object across all active facts — consolidated, not a conflict",
            )

        # Genuine conflict: differing objects.
        max_observed_at = max(f.observed_at for f in active)
        at_max = [f for f in active if f.observed_at == max_observed_at]
        objects_at_max = {f.object for f in at_max}

        if len(objects_at_max) > 1:
            # Same-timestamp, different-object — not a forced guess.
            return ConflictResolution(
                subject=subject, predicate=predicate, winning_fact=None,
                resolution_method=ResolutionMethod.UNRESOLVED, unresolved=True,
                version_history=all_facts,
                reason=(
                    f"{len(at_max)} facts share the newest observed_at "
                    f"({max_observed_at.isoformat()}) with differing objects — genuinely ambiguous"
                ),
            )

        winner = at_max[0]
        losers = [f for f in active if f.id != winner.id]
        self._consolidate(subject, predicate, winner, losers, reason="newer_observed_at_wins")

        return ConflictResolution(
            subject=subject, predicate=predicate, winning_fact=winner,
            resolution_method=ResolutionMethod.DETERMINISTIC, unresolved=False,
            version_history=all_facts, newly_superseded_ids=[loser.id for loser in losers],
            reason="unique newest observed_at among differing objects",
        )

    def _consolidate(self, subject: str, predicate: str, winner: Fact, losers: list[Fact], reason: str) -> None:
        if not losers:
            return
        for loser in losers:
            self.store.set_status(loser.id, FactStatus.SUPERSEDED)
        immediate_prior = max(losers, key=lambda f: f.observed_at)
        self.store.set_supersedes(winner.id, immediate_prior.id)
        self.store.set_resolution_method(winner.id, ResolutionMethod.DETERMINISTIC)
        self.store.log_supersession_event(
            subject=subject, predicate=predicate, winning_fact_id=winner.id,
            superseded_fact_ids=[loser.id for loser in losers],
            method="deterministic_timestamp", reason=reason,
        )
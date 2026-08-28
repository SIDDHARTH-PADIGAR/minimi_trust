"""
Deterministic Conflict Detector (M2, §2 Control Plane).

Timestamp/versioning logic, subject+predicate exact matching. No
embeddings, no semantic candidate matching (that's M3 — see
semantic_detector.py, which reuses resolve_facts() below unchanged),
no LLM arbitration (M4).

resolve_conflict() and resolve_facts() are split so M3 can hand this
class a broader, similarity-matched fact list without duplicating or
changing the resolution algorithm itself.

M7: both public methods hold store.operation_lock for their full body,
so a concurrent caller can't observe or mutate the same subject+predicate
mid-resolution. RLock — safe to reenter from resolve_conflict into
resolve_facts on the same thread.
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
        with self.store.operation_lock:
            facts = self.store.get_facts(subject, predicate)
            return self.resolve_facts(subject, predicate, facts)

    def resolve_facts(self, subject: str, predicate: str, all_facts: list[Fact]) -> ConflictResolution:
        with self.store.operation_lock:
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
                winner = max(active, key=lambda f: (f.observed_at, f.extracted_at, f.id))
                losers = [f for f in active if f.id != winner.id]
                self._consolidate(subject, predicate, winner, losers, reason="redundant_consolidation")
                return ConflictResolution(
                    subject=subject, predicate=predicate, winning_fact=winner,
                    resolution_method=ResolutionMethod.DETERMINISTIC, unresolved=False,
                    version_history=all_facts, newly_superseded_ids=[loser.id for loser in losers],
                    reason="identical object across all active facts — consolidated, not a conflict",
                )

            max_observed_at = max(f.observed_at for f in active)
            at_max = [f for f in active if f.observed_at == max_observed_at]
            objects_at_max = {f.object for f in at_max}

            if len(objects_at_max) > 1:
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
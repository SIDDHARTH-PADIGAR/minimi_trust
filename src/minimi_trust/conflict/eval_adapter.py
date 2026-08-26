"""
Adapts the M2 ConflictDetector to the (Scenario) -> (unresolved, object)
resolver contract used by eval/harness.py, so M2 is scored with the exact
same harness as the M1 baselines — a fair, apples-to-apples delta.

Each scenario gets its own fresh in-memory FactStore: the detector is
scored per-scenario, not accumulating state across the dataset.
"""

from __future__ import annotations

from typing import Optional

from minimi_trust.conflict.detector import ConflictDetector
from minimi_trust.eval.loader import Scenario
from minimi_trust.store.fact_store import FactStore


def deterministic_conflict_resolver(scenario: Scenario) -> tuple[bool, Optional[str]]:
    with FactStore(":memory:") as store:
        for fact in scenario.facts:
            store.add_fact(fact)
        detector = ConflictDetector(store)
        result = detector.resolve_conflict(scenario.query.subject, scenario.query.predicate)
        winning_object = result.winning_fact.object if result.winning_fact else None
        return result.unresolved, winning_object
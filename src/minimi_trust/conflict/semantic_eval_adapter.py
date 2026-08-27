"""
Adapts the M3 SemanticConflictDetector to the eval harness resolver
contract, mirroring conflict/eval_adapter.py (M2).
"""

from __future__ import annotations

from typing import Optional

from minimi_trust.conflict.semantic_detector import SemanticConflictDetector
from minimi_trust.eval.loader import Scenario
from minimi_trust.store.fact_store import FactStore


def semantic_conflict_resolver(scenario: Scenario) -> tuple[bool, Optional[str]]:
    with FactStore(":memory:") as store:
        for fact in scenario.facts:
            store.add_fact(fact)
        detector = SemanticConflictDetector(store)
        result = detector.resolve_conflict(scenario.query.subject, scenario.query.predicate)
        winning_object = result.winning_fact.object if result.winning_fact else None
        return result.unresolved, winning_object
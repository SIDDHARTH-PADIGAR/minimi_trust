"""
Adapts the M5 DeletionVerificationEngine to a scenario -> prediction
mapping for scoring, mirroring the conflict-track eval adapters (M2/M3).
"""

from __future__ import annotations

from minimi_trust.deletion.engine import DeletionVerificationEngine
from minimi_trust.eval.deletion_loader import DeletionScenario
from minimi_trust.store.fact_store import FactStore


def run_deletion_scenario(scenario: DeletionScenario) -> dict:
    with FactStore(":memory:") as store:
        store.add_fact(scenario.target_fact)
        for artifact in scenario.derived_artifacts:
            store.add_derived_artifact(scenario.target_fact.id, artifact.kind, artifact.ref, artifact.note)

        engine = DeletionVerificationEngine(store)
        report = engine.verify_deletion(
            scenario.target_fact.id,
            simulate_primary_deletion_failure=scenario.simulate_primary_deletion_failure,
        )

    return {
        "scenario_id": scenario.scenario_id,
        "category": scenario.category,
        "predicted_verification_result": report.verification_result.value,
        "predicted_residual_recoverability_score": report.residual_recoverability_score,
        "cascade_trace": [t.model_dump() for t in report.cascade_trace],
    }
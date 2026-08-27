"""
M5 unit tests for the DeletionVerificationEngine, independent of the
eval harness — these test actual FactStore mutations (redaction, status
transitions, artifact neutralization), not just the returned DeletionReport.
"""

from datetime import datetime, timezone

from minimi_trust.deletion.engine import DeletionVerificationEngine
from minimi_trust.schemas import Fact, FactStatus, VerificationResult
from minimi_trust.store.fact_store import FactStore


def _fact(fact_id="fact_test_001"):
    return Fact(
        id=fact_id, subject="x", predicate="is", object="secret_value",
        source_document_id="src_test", observed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        extracted_at=datetime(2026, 1, 1, tzinfo=timezone.utc), confidence=0.9,
    )


def test_clean_deletion_has_no_residuals():
    with FactStore(":memory:") as store:
        store.add_fact(_fact())
        report = DeletionVerificationEngine(store).verify_deletion("fact_test_001")
        assert report.verification_result == VerificationResult.VERIFIED_DELETED
        assert report.residual_recoverability_score == 0.0
        redacted = store.get_facts("x", "is")[0]
        assert redacted.object == "[REDACTED]"
        assert redacted.status == FactStatus.DELETION_VERIFIED


def test_trackable_dependent_fact_gets_neutralized_not_just_flagged():
    with FactStore(":memory:") as store:
        store.add_fact(_fact())
        store.add_derived_artifact("fact_test_001", "dependent_fact", "summary_ref_1", "a derived summary")
        report = DeletionVerificationEngine(store).verify_deletion("fact_test_001")
        assert report.verification_result == VerificationResult.VERIFIED_DELETED
        assert report.residual_recoverability_score == 0.0
        assert store.get_derived_artifacts("fact_test_001") == []


def test_untrackable_embedding_artifact_is_flagged_not_purged():
    with FactStore(":memory:") as store:
        store.add_fact(_fact())
        store.add_derived_artifact("fact_test_001", "embedding_index", "emb_ref_1", "vector entry")
        report = DeletionVerificationEngine(store).verify_deletion("fact_test_001")
        assert report.verification_result == VerificationResult.RESIDUAL_RISK_FOUND
        assert report.residual_recoverability_score == 1.0
        assert len(report.cascade_trace) == 1
        assert len(store.get_derived_artifacts("fact_test_001")) == 1  # still present — not purged


def test_mixed_artifacts_score_reflects_only_untrackable_fraction():
    with FactStore(":memory:") as store:
        store.add_fact(_fact())
        store.add_derived_artifact("fact_test_001", "dependent_fact", "summary_ref_1")
        store.add_derived_artifact("fact_test_001", "embedding_index", "emb_ref_1")
        report = DeletionVerificationEngine(store).verify_deletion("fact_test_001")
        assert report.verification_result == VerificationResult.RESIDUAL_RISK_FOUND
        assert report.residual_recoverability_score == 0.5


def test_simulated_primary_failure_never_reaches_verification():
    with FactStore(":memory:") as store:
        store.add_fact(_fact())
        report = DeletionVerificationEngine(store).verify_deletion(
            "fact_test_001", simulate_primary_deletion_failure=True
        )
        assert report.verification_result == VerificationResult.DELETION_INCOMPLETE
        assert report.residual_recoverability_score is None
        still_pending = store.get_facts("x", "is")[0]
        assert still_pending.status == FactStatus.DELETION_PENDING
        assert still_pending.object == "secret_value"  # never redacted
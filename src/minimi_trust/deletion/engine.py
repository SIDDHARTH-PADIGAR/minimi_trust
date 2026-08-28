"""
Deletion + Verification Engine (M5, §2 Control Plane / §3 DeletionReport / §4 verify_deletion).

Moves a fact through status=DELETION_PENDING -> attempts primary-record
redaction -> traces derived artifacts genuinely tracked in the Fact
Store (not read from a scenario's ground truth) -> reports a
DeletionReport with a measured cascade trace and residual-recoverability
score, per §3's "measured, not asserted" instruction.

Two kinds of derived artifact are modeled differently, reflecting a
real, documented limitation (MemLeak) rather than assuming it away:
  - "dependent_fact"                — this system's OWN derived facts.
                                       The engine CAN discover and
                                       neutralize these.
  - "embedding_index" / "index_entry" — external index/embedding-store
                                       residuals. The engine CAN detect
                                       that they were logged at ingestion
                                       time but CANNOT purge them.

M7: the full body is held under store.operation_lock — two concurrent
verify_deletion calls on the same fact could otherwise double-neutralize
artifacts or race on the fact's status transitions.
"""

from __future__ import annotations

from minimi_trust.schemas import CascadeTraceEntry, DeletionReport, FactStatus, VerificationResult
from minimi_trust.store.fact_store import FactStore

UNTRACKABLE_ARTIFACT_KINDS = {"embedding_index", "index_entry"}


class DeletionVerificationEngine:
    def __init__(self, store: FactStore):
        self.store = store

    def verify_deletion(self, target_fact_id: str, simulate_primary_deletion_failure: bool = False) -> DeletionReport:
        with self.store.operation_lock:
            self.store.set_status(target_fact_id, FactStatus.DELETION_PENDING)
            self.store.log_deletion_event(target_fact_id, "deletion_requested")

            if simulate_primary_deletion_failure:
                self.store.log_deletion_event(target_fact_id, "primary_deletion_failed")
                return DeletionReport(
                    target_fact_id=target_fact_id,
                    cascade_trace=[],
                    residual_recoverability_score=None,
                    verification_result=VerificationResult.DELETION_INCOMPLETE,
                )

            self.store.redact_fact(target_fact_id)
            self.store.log_deletion_event(target_fact_id, "primary_record_redacted")

            artifacts = self.store.get_derived_artifacts(target_fact_id)
            cascade_trace: list[CascadeTraceEntry] = []
            untrackable_count = 0

            for artifact in artifacts:
                note = artifact["note"] or ""
                if artifact["kind"] in UNTRACKABLE_ARTIFACT_KINDS:
                    untrackable_count += 1
                    cascade_trace.append(CascadeTraceEntry(
                        kind=artifact["kind"], ref=artifact["ref"],
                        note=f"{note} [detected, not purgeable by this engine]".strip(),
                    ))
                else:
                    self.store.neutralize_derived_artifact(artifact["id"])
                    cascade_trace.append(CascadeTraceEntry(
                        kind=artifact["kind"], ref=artifact["ref"],
                        note=f"{note} [found and neutralized]".strip(),
                    ))

            total_found = len(artifacts)
            residual_score = (untrackable_count / total_found) if total_found else 0.0

            result = VerificationResult.RESIDUAL_RISK_FOUND if untrackable_count else VerificationResult.VERIFIED_DELETED
            self.store.set_status(target_fact_id, FactStatus.DELETION_VERIFIED)

            self.store.log_deletion_event(target_fact_id, "verification_completed", {
                "verification_result": result.value, "residual_recoverability_score": residual_score,
            })

            return DeletionReport(
                target_fact_id=target_fact_id, cascade_trace=cascade_trace,
                residual_recoverability_score=residual_score, verification_result=result,
            )
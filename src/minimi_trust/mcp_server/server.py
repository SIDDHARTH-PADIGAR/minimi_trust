"""
MCP Server (M6, §4).

Wraps M4's conflict/correction path (TargetedLLMArbitrator, itself
wrapping M2 deterministic + M3 semantic matching), M5's Deletion +
Verification Engine, and the minimal Recall/Explain layer, behind the
four tools specified in §4. propose_correction and verify_deletion are
the only tools that mutate the Fact Store; resolve_conflict's only
mutation is the supersession record already produced by the detectors
it wraps; explain_retrieval never mutates anything.

build_server_with_store() (M7) returns (mcp, store) so tests can seed
custom data and inspect the store/event log after tool calls —
build_server() wraps it and keeps its original signature/behavior for
existing callers.
"""

from __future__ import annotations

import os
from typing import Optional

from fastmcp import FastMCP

from minimi_trust.conflict.llm_arbitrator import TargetedLLMArbitrator
from minimi_trust.deletion.engine import DeletionVerificationEngine
from minimi_trust.mcp_server.seed import seed_demo_data_if_empty
from minimi_trust.recall.index import RecallIndex
from minimi_trust.schemas import CorrectionProposal, Fact
from minimi_trust.store.fact_store import FactStore

DEFAULT_DB_PATH = os.environ.get("MINIMI_DB_PATH", "minimi_trust.db")


def _fact_to_dict(fact: Fact) -> dict:
    return {
        "id": fact.id, "subject": fact.subject, "predicate": fact.predicate, "object": fact.object,
        "raw_text": fact.raw_text, "source_document_id": fact.source_document_id,
        "observed_at": fact.observed_at.isoformat(), "extracted_at": fact.extracted_at.isoformat(),
        "confidence": fact.confidence, "status": fact.status.value,
        "supersedes_id": fact.supersedes_id, "resolution_method": fact.resolution_method.value,
    }


def build_server_with_store(db_path: str = DEFAULT_DB_PATH, store: Optional[FactStore] = None) -> tuple[FastMCP, FactStore]:
    if store is None:
        store = FactStore(db_path)
        seed_demo_data_if_empty(store)

    mcp = FastMCP("minimi-trust-layer")

    @mcp.tool()
    def resolve_conflict(subject: str, predicate: str) -> dict:
        """Resolve which fact is currently true for a given subject+predicate.
        Runs deterministic timestamp logic first (M2), broadens the candidate
        set via semantic subject/predicate matching (M3), and escalates to a
        targeted LLM arbitration only when still genuinely ambiguous (M4).
        Returns the winning fact (or none, if unresolved), the full version
        history including superseded facts, and which resolution method was
        actually used. Never silently deletes a losing fact."""
        result = TargetedLLMArbitrator(store).resolve_conflict(subject, predicate)
        return {
            "subject": subject, "predicate": predicate,
            "unresolved": result.unresolved, "winning_object": result.winning_object,
            "resolution_method": result.resolution_method.value,
            "escalated_to_llm": result.escalated,
            "reason": result.base.reason,
            "version_history": [_fact_to_dict(f) for f in result.base.version_history],
        }

    @mcp.tool()
    def propose_correction(target_fact_id: str, proposed_object: str, rationale: str) -> dict:
        """Create a pending correction proposal for a fact. Writes ONLY the
        proposal record — the target fact itself is never modified by this
        tool. Accept/reject is a separate administrative step, intentionally
        not exposed here, to keep the MCP surface exactly the four §4 tools."""
        target = store.get_fact_by_id(target_fact_id)
        if target is None:
            return {"error": "fact not found", "target_fact_id": target_fact_id}

        proposal = CorrectionProposal(
            target_fact_id=target_fact_id, proposed_object=proposed_object, rationale=rationale,
        )
        store.add_proposal(proposal)
        return {"proposal_id": proposal.id, "target_fact_id": target_fact_id, "status": proposal.status.value}

    @mcp.tool()
    def verify_deletion(target_fact_id: str) -> dict:
        """Delete a fact and verify what actually happened — moves it through
        deletion_pending, redacts the primary record, traces derived artifacts
        this system actually tracks, and reports a measured
        residual-recoverability score. deletion_incomplete and
        residual_risk_found are valid, expected outcomes, not bugs."""
        target = store.get_fact_by_id(target_fact_id)
        if target is None:
            return {"error": "fact not found", "target_fact_id": target_fact_id}

        report = DeletionVerificationEngine(store).verify_deletion(target_fact_id)
        return {
            "target_fact_id": target_fact_id,
            "verification_result": report.verification_result.value,
            "residual_recoverability_score": report.residual_recoverability_score,
            "cascade_trace": [t.model_dump() for t in report.cascade_trace],
        }

    @mcp.tool()
    def explain_retrieval(query: str, top_k: int = 5) -> dict:
        """Search current (active, non-deleted) facts for the given free-text
        query and annotate every result with provenance, confidence,
        staleness, and whether it has an unresolved conflict. Read-only
        against the control plane's current-state snapshot — never mutates
        memory as a side effect of being read."""
        index = RecallIndex(store)
        return {"query": query, "results": index.search(query, top_k=top_k)}

    return mcp, store


def build_server(db_path: str = DEFAULT_DB_PATH) -> FastMCP:
    mcp, _ = build_server_with_store(db_path)
    return mcp


mcp = build_server()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
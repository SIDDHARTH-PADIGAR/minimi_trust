"""
Data schemas for the MCP-Native Memory Trust/Correction System.

Scope: M0 — schema definitions only. No conflict-detection, supersession,
or deletion LOGIC lives here. The only validation enforced is structural
data integrity explicitly called out in the build plan (§3): extracted_at
can never precede observed_at.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# --------------------------------------------------------------------------
# Enums
# --------------------------------------------------------------------------

class FactStatus(str, Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    DELETION_PENDING = "deletion_pending"
    DELETION_VERIFIED = "deletion_verified"


class ResolutionMethod(str, Enum):
    DETERMINISTIC = "deterministic"
    LLM_ARBITRATED = "llm_arbitrated"
    UNRESOLVED = "unresolved"


class SourceType(str, Enum):
    DOC = "doc"
    TRANSCRIPT = "transcript"
    NOTE = "note"


class ProposalStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class VerificationResult(str, Enum):
    PENDING = "pending"  # addition beyond §3 — pre-verification state
    VERIFIED_DELETED = "verified_deleted"
    RESIDUAL_RISK_FOUND = "residual_risk_found"
    DELETION_INCOMPLETE = "deletion_incomplete"


class DataLabel(str, Enum):
    """Enforced per build plan §5 — every dataset row states its provenance."""
    REAL_DATA = "REAL DATA"
    SIMULATED_DATA = "SIMULATED DATA"
    SELF_AUTHORED_EVALUATION_DATA = "SELF-AUTHORED EVALUATION DATA"


# --------------------------------------------------------------------------
# Core entities (§3 Data Model)
# --------------------------------------------------------------------------

class SourceDocument(BaseModel):
    id: str = Field(default_factory=lambda: _new_id("src"))
    type: SourceType
    raw_text: str
    ingested_at: datetime = Field(default_factory=_now)
    content_hash: str


class Fact(BaseModel):
    id: str = Field(default_factory=lambda: _new_id("fact"))
    subject: str
    predicate: str
    object: str
    raw_text: Optional[str] = None  # fallback for anything extraction can't triple-ify

    source_document_id: str
    observed_at: datetime          # when the fact was true / stated
    extracted_at: datetime         # when the system ingested it; always >= observed_at

    confidence: float = Field(ge=0.0, le=1.0)
    status: FactStatus = FactStatus.ACTIVE
    supersedes_id: Optional[str] = None
    resolution_method: ResolutionMethod = ResolutionMethod.UNRESOLVED
    embedding_ref: Optional[str] = None

    @model_validator(mode="after")
    def _extracted_after_observed(self) -> "Fact":
        if self.extracted_at < self.observed_at:
            raise ValueError(
                f"extracted_at ({self.extracted_at}) precedes observed_at "
                f"({self.observed_at}) for fact {self.id}"
            )
        return self


class CorrectionProposal(BaseModel):
    id: str = Field(default_factory=lambda: _new_id("prop"))
    target_fact_id: str
    proposed_object: str
    rationale: str
    status: ProposalStatus = ProposalStatus.PENDING
    created_at: datetime = Field(default_factory=_now)
    resolved_at: Optional[datetime] = None


class CascadeTraceEntry(BaseModel):
    """One derived representation found while tracing a deletion."""
    kind: str            # e.g. "embedding", "dependent_fact", "index_entry"
    ref: str              # id/pointer to the derived representation
    note: Optional[str] = None


class DeletionReport(BaseModel):
    id: str = Field(default_factory=lambda: _new_id("del"))
    target_fact_id: str
    requested_at: datetime = Field(default_factory=_now)
    cascade_trace: list[CascadeTraceEntry] = Field(default_factory=list)
    residual_recoverability_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    verification_result: VerificationResult = VerificationResult.PENDING
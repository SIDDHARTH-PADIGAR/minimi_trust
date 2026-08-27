"""
M5 dataset loader for deletion-track scenarios.

Each scenario inserts a REAL target Fact plus REAL derived-artifact
specs into a FactStore; the DeletionVerificationEngine discovers
residuals by querying the store, not by reading this file's
ground_truth block — that block exists only to score the engine's
output, never to inform it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator, Optional

from pydantic import BaseModel, Field

from minimi_trust.schemas import DataLabel, Fact, VerificationResult

DEFAULT_DELETION_PATH = Path("data/track2_self_authored/deletion_scenarios.jsonl")


class DerivedArtifactSpec(BaseModel):
    kind: str
    ref: str
    note: Optional[str] = None


class DeletionGroundTruth(BaseModel):
    expected_verification_result: VerificationResult
    expected_residual_recoverability_score: Optional[float] = None


class DeletionScenario(BaseModel):
    scenario_id: str
    category: str
    label: DataLabel
    target_fact: Fact
    derived_artifacts: list[DerivedArtifactSpec] = Field(default_factory=list)
    simulate_primary_deletion_failure: bool = False
    ground_truth: DeletionGroundTruth


def load_deletion_scenarios(path: Path = DEFAULT_DELETION_PATH) -> Iterator[DeletionScenario]:
    # utf-8-sig: see loader.py — transparently strips a leading BOM.
    with path.open("r", encoding="utf-8-sig") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield DeletionScenario.model_validate_json(line)
            except Exception as exc:
                raise ValueError(f"{path}:{line_no}: invalid deletion scenario — {exc}") from exc
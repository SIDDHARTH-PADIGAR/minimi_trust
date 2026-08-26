"""
M1 dataset loader for deletion-track scenarios.

Distinct shape from conflict scenarios: no subject+predicate query, no
list of competing facts to arbitrate. Each row describes a single target
fact plus the *known* residual locations a correct verifier should find,
and the ground truth for what an honest verification_result should be.

This does not require a real Fact Store or Deletion Engine (that's M5) —
scenarios are self-describing so a baseline, and later the real engine,
can be scored against them directly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

from pydantic import BaseModel

from minimi_trust.schemas import DataLabel, VerificationResult

DEFAULT_DELETION_PATH = Path("data/track2_self_authored/deletion_scenarios.jsonl")


class DeletionGroundTruth(BaseModel):
    residual_recoverable: bool
    expected_verification_result: VerificationResult


class DeletionScenario(BaseModel):
    scenario_id: str
    category: str
    label: DataLabel
    target_fact_id: str
    target_fact_summary: str
    known_residual_locations: list[str]  # e.g. "embedding_index:...", "dependent_fact:..."
    ground_truth: DeletionGroundTruth


def load_deletion_scenarios(path: Path = DEFAULT_DELETION_PATH) -> Iterator[DeletionScenario]:
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield DeletionScenario.model_validate_json(line)
            except Exception as exc:
                raise ValueError(f"{path}:{line_no}: invalid deletion scenario — {exc}") from exc
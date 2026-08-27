"""
M0 dataset loader for Track 2 (self-authored, resolve_conflict-shaped)
scenarios.

Track 1 (MemoryAgentBench) is intentionally NOT wired up yet — see
data/track1_memoryagentbench/README_SOURCE.md. Deletion-shaped scenarios
are also out of scope here; they have their own loader (deletion_loader.py).
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator, Optional

from pydantic import BaseModel

from minimi_trust.schemas import DataLabel, Fact, ResolutionMethod


class ScenarioQuery(BaseModel):
    subject: str
    predicate: str


class ScenarioGroundTruth(BaseModel):
    winning_object: Optional[str] = None
    resolution_method: Optional[ResolutionMethod] = None
    unresolved: bool = False


class Scenario(BaseModel):
    scenario_id: str
    category: str
    label: DataLabel
    facts: list[Fact]
    query: ScenarioQuery
    ground_truth: ScenarioGroundTruth


def load_track2_scenarios(path: Path) -> Iterator[Scenario]:
    # utf-8-sig: transparently strips a leading BOM if present (e.g. from
    # PowerShell's Set-Content -Encoding utf8), behaves like plain utf-8
    # otherwise. Prevents a silent "line 1: invalid JSON" failure mode.
    with path.open("r", encoding="utf-8-sig") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield Scenario.model_validate_json(line)
            except Exception as exc:  # surfaced, not swallowed
                raise ValueError(f"{path}:{line_no}: invalid scenario — {exc}") from exc
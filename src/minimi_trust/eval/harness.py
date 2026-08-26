"""
M0 eval harness — proves the loop runs end-to-end, nothing more.

Per the build plan, M0's only job is: does the harness run against
known-answer data and report a score, even a trivial/wrong one. The
resolver below is a deliberate stub — it's replaced by real baselines
starting at M1, deterministic logic at M2/M3, and LLM arbitration at M4.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from minimi_trust.eval.loader import Scenario, load_track2_scenarios

DEFAULT_TRACK2_PATH = Path("data/track2_self_authored/scenarios.jsonl")
DEFAULT_RESULTS_DIR = Path("results")

Resolver = Callable[[Scenario], "tuple[bool, Optional[str]]"]


@dataclass
class ScenarioResult:
    scenario_id: str
    category: str
    predicted_unresolved: bool
    predicted_object: Optional[str]
    correct: bool


@dataclass
class HarnessReport:
    baseline_name: str
    total: int
    correct: int
    results: list[ScenarioResult] = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0

    def to_dict(self) -> dict:
        return {
            "baseline_name": self.baseline_name,
            "total": self.total,
            "correct": self.correct,
            "accuracy": self.accuracy,
            "results": [r.__dict__ for r in self.results],
        }


def stub_resolver(scenario: Scenario) -> tuple[bool, Optional[str]]:
    """M0 placeholder. Always reports unresolved — real logic starts M1+."""
    return True, None


def run(
    track2_path: Path = DEFAULT_TRACK2_PATH,
    resolver: Resolver = stub_resolver,
    baseline_name: str = "m0_stub",
) -> HarnessReport:
    scenarios = list(load_track2_scenarios(track2_path))
    results: list[ScenarioResult] = []
    correct = 0

    for scenario in scenarios:
        predicted_unresolved, predicted_object = resolver(scenario)
        is_correct = (
            predicted_unresolved == scenario.ground_truth.unresolved
            and (predicted_unresolved or predicted_object == scenario.ground_truth.winning_object)
        )
        if is_correct:
            correct += 1
        results.append(
            ScenarioResult(
                scenario_id=scenario.scenario_id,
                category=scenario.category,
                predicted_unresolved=predicted_unresolved,
                predicted_object=predicted_object,
                correct=is_correct,
            )
        )

    return HarnessReport(baseline_name=baseline_name, total=len(scenarios), correct=correct, results=results)


def main() -> None:
    report = run()
    DEFAULT_RESULTS_DIR.mkdir(exist_ok=True)
    out_path = DEFAULT_RESULTS_DIR / f"{report.baseline_name}.json"
    out_path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    print(
        f"[{report.baseline_name}] {report.correct}/{report.total} correct "
        f"({report.accuracy:.1%}) — written to {out_path}"
    )


if __name__ == "__main__":
    main()
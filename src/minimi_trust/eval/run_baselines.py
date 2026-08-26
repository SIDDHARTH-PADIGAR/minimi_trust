"""
M1 entrypoint — runs every §6 baseline against Track 2 and writes one
result file per baseline. This is the first milestone that produces real,
comparable numbers; every later milestone is measured against these.

Track 1 (MemoryAgentBench) is not run here yet — the raw benchmark has
been cloned locally but not reformatted into this project's Scenario
shape (see data/track1_memoryagentbench/README_SOURCE.md). Flagged
explicitly rather than silently skipped.
"""

from __future__ import annotations

import json
from pathlib import Path

from minimi_trust.eval.baselines import (
    naive_delete_predict,
    naive_overwrite_resolver,
    pure_deterministic_resolver,
)
from minimi_trust.eval.deletion_loader import DEFAULT_DELETION_PATH, load_deletion_scenarios
from minimi_trust.eval.harness import DEFAULT_RESULTS_DIR, DEFAULT_TRACK2_PATH, run


def run_deletion_baseline(path: Path = DEFAULT_DELETION_PATH) -> dict:
    scenarios = list(load_deletion_scenarios(path))
    correct = 0
    results = []
    for scenario in scenarios:
        predicted = naive_delete_predict(scenario)
        is_correct = predicted == scenario.ground_truth.expected_verification_result.value
        if is_correct:
            correct += 1
        results.append(
            {
                "scenario_id": scenario.scenario_id,
                "category": scenario.category,
                "predicted_verification_result": predicted,
                "expected_verification_result": scenario.ground_truth.expected_verification_result.value,
                "correct": is_correct,
            }
        )
    total = len(scenarios)
    return {
        "baseline_name": "naive_delete",
        "total": total,
        "correct": correct,
        "accuracy": correct / total if total else 0.0,
        "results": results,
    }


def main() -> None:
    DEFAULT_RESULTS_DIR.mkdir(exist_ok=True)
    summary = []

    conflict_baselines = {
        "naive_overwrite": naive_overwrite_resolver,
        "pure_deterministic": pure_deterministic_resolver,
    }

    try:
        from minimi_trust.eval.baselines import make_pure_llm_resolver
        conflict_baselines["pure_llm"] = make_pure_llm_resolver()
    except Exception as exc:
        print(f"[skip] pure_llm baseline not run — {exc}")

    for name, resolver in conflict_baselines.items():
        report = run(track2_path=DEFAULT_TRACK2_PATH, resolver=resolver, baseline_name=name)
        out_path = DEFAULT_RESULTS_DIR / f"{name}.json"
        out_path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
        summary.append((name, report.total, report.correct, report.accuracy))
        print(f"[{name}] {report.correct}/{report.total} correct ({report.accuracy:.1%}) — {out_path}")

    deletion_report = run_deletion_baseline()
    out_path = DEFAULT_RESULTS_DIR / "naive_delete.json"
    out_path.write_text(json.dumps(deletion_report, indent=2), encoding="utf-8")
    summary.append(("naive_delete", deletion_report["total"], deletion_report["correct"], deletion_report["accuracy"]))
    print(
        f"[naive_delete] {deletion_report['correct']}/{deletion_report['total']} correct "
        f"({deletion_report['accuracy']:.1%}) — {out_path}"
    )

    print("\nM1 summary (Track 2 only — Track 1 reformat still TBD):")
    for name, total, correct, acc in summary:
        print(f"  {name:<20} {correct}/{total}  {acc:.1%}")


if __name__ == "__main__":
    main()
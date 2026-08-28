"""
M8 — unified final evaluation report.

Reruns EVERY baseline and EVERY milestone's resolver fresh, on the
CURRENT dataset, in one pass. Earlier per-milestone entrypoints
(run_baselines.py, run_m2.py, run_m3.py, run_m4.py, run_m5.py) each ran
correctly at the time, but the Track 2 dataset grew across milestones
(8 -> 10 -> 11 scenarios) as new cases were added to exercise each new
mechanism — so numbers reported at different points in the build are
NOT directly comparable to each other. This script produces one single,
apples-to-apples comparison table on today's dataset, for the README.
"""

from __future__ import annotations

import json

from minimi_trust.conflict.eval_adapter import deterministic_conflict_resolver
from minimi_trust.conflict.semantic_eval_adapter import semantic_conflict_resolver
from minimi_trust.deletion.eval_adapter import run_deletion_scenario
from minimi_trust.eval.baselines import (
    make_pure_llm_resolver,
    naive_delete_predict,
    naive_overwrite_resolver,
    pure_deterministic_resolver,
)
from minimi_trust.eval.deletion_loader import DEFAULT_DELETION_PATH, load_deletion_scenarios
from minimi_trust.eval.harness import DEFAULT_RESULTS_DIR, run
from minimi_trust.eval.run_m4 import run_m4


def run_track2_suite() -> dict:
    reports: dict = {}
    reports["naive_overwrite"] = run(resolver=naive_overwrite_resolver, baseline_name="naive_overwrite").to_dict()
    reports["pure_deterministic"] = run(resolver=pure_deterministic_resolver, baseline_name="pure_deterministic").to_dict()
    try:
        reports["pure_llm"] = run(resolver=make_pure_llm_resolver(), baseline_name="pure_llm").to_dict()
    except Exception as exc:
        reports["pure_llm"] = {"skipped": str(exc)}
    reports["m2_deterministic_conflict_detection"] = run(
        resolver=deterministic_conflict_resolver, baseline_name="m2_deterministic_conflict_detection"
    ).to_dict()
    reports["m3_semantic_candidate_matching"] = run(
        resolver=semantic_conflict_resolver, baseline_name="m3_semantic_candidate_matching"
    ).to_dict()
    reports["m4_targeted_llm_arbitration"] = run_m4()
    return reports


def run_deletion_suite() -> dict:
    scenarios = list(load_deletion_scenarios(DEFAULT_DELETION_PATH))
    total = len(scenarios)

    naive_correct = 0
    naive_results = []
    for s in scenarios:
        predicted = naive_delete_predict(s)
        correct = predicted == s.ground_truth.expected_verification_result.value
        naive_correct += int(correct)
        naive_results.append({"scenario_id": s.scenario_id, "correct": correct})

    m5_correct = 0
    m5_results = []
    for s in scenarios:
        prediction = run_deletion_scenario(s)
        result_ok = prediction["predicted_verification_result"] == s.ground_truth.expected_verification_result.value
        score_ok = True
        if s.ground_truth.expected_residual_recoverability_score is not None:
            score_ok = (
                prediction["predicted_residual_recoverability_score"]
                == s.ground_truth.expected_residual_recoverability_score
            )
        correct = result_ok and score_ok
        m5_correct += int(correct)
        prediction["correct"] = correct
        m5_results.append(prediction)

    return {
        "naive_delete": {"total": total, "correct": naive_correct, "accuracy": naive_correct / total, "results": naive_results},
        "m5_deletion_verification_engine": {
            "total": total, "correct": m5_correct, "accuracy": m5_correct / total, "results": m5_results,
        },
    }


def main() -> None:
    DEFAULT_RESULTS_DIR.mkdir(exist_ok=True)
    track2 = run_track2_suite()
    deletion = run_deletion_suite()

    final = {"track2": track2, "deletion": deletion}
    (DEFAULT_RESULTS_DIR / "final_report.json").write_text(json.dumps(final, indent=2), encoding="utf-8")

    print("=" * 70)
    print("TRACK 2 — conflict resolution (self-authored)")
    print("=" * 70)
    for name, report in track2.items():
        if report.get("skipped"):
            print(f"  {name:<40} SKIPPED — {report['skipped']}")
            continue
        print(f"  {name:<40} {report['correct']}/{report['total']} correct ({report['accuracy']:.1%})")
        if "escalation_rate" in report:
            print(f"  {'':<40} escalation rate: {report['escalated_count']}/{report['total']} ({report['escalation_rate']:.1%})")

    print()
    print("=" * 70)
    print("DELETION TRACK — cascade verification (self-authored)")
    print("=" * 70)
    for name, report in deletion.items():
        print(f"  {name:<40} {report['correct']}/{report['total']} correct ({report['accuracy']:.1%})")

    print()
    print(f"Full detail written to {DEFAULT_RESULTS_DIR / 'final_report.json'}")


if __name__ == "__main__":
    main()
"""
M5 entrypoint — runs the real Deletion + Verification Engine against the
redesigned deletion scenarios and reports the delta over baseline 4
(naive_delete), per the build plan's explicit instruction for this
milestone.
"""

from __future__ import annotations

import json

from minimi_trust.deletion.eval_adapter import run_deletion_scenario
from minimi_trust.eval.baselines import naive_delete_predict
from minimi_trust.eval.deletion_loader import DEFAULT_DELETION_PATH, load_deletion_scenarios
from minimi_trust.eval.harness import DEFAULT_RESULTS_DIR


def main() -> None:
    DEFAULT_RESULTS_DIR.mkdir(exist_ok=True)
    scenarios = list(load_deletion_scenarios(DEFAULT_DELETION_PATH))
    total = len(scenarios)

    naive_results = []
    naive_correct = 0
    for scenario in scenarios:
        predicted = naive_delete_predict(scenario)
        is_correct = predicted == scenario.ground_truth.expected_verification_result.value
        if is_correct:
            naive_correct += 1
        naive_results.append({
            "scenario_id": scenario.scenario_id, "category": scenario.category,
            "predicted_verification_result": predicted, "correct": is_correct,
        })

    m5_results = []
    m5_correct = 0
    for scenario in scenarios:
        prediction = run_deletion_scenario(scenario)
        result_correct = prediction["predicted_verification_result"] == scenario.ground_truth.expected_verification_result.value
        score_correct = True
        if scenario.ground_truth.expected_residual_recoverability_score is not None:
            score_correct = (
                prediction["predicted_residual_recoverability_score"]
                == scenario.ground_truth.expected_residual_recoverability_score
            )
        is_correct = result_correct and score_correct
        if is_correct:
            m5_correct += 1
        prediction["correct"] = is_correct
        m5_results.append(prediction)

    naive_report = {
        "baseline_name": "naive_delete", "total": total, "correct": naive_correct,
        "accuracy": naive_correct / total if total else 0.0, "results": naive_results,
    }
    m5_report = {
        "baseline_name": "m5_deletion_verification_engine", "total": total, "correct": m5_correct,
        "accuracy": m5_correct / total if total else 0.0, "results": m5_results,
    }

    (DEFAULT_RESULTS_DIR / "naive_delete.json").write_text(json.dumps(naive_report, indent=2), encoding="utf-8")
    (DEFAULT_RESULTS_DIR / "m5_deletion_verification_engine.json").write_text(json.dumps(m5_report, indent=2), encoding="utf-8")

    delta = m5_report["accuracy"] - naive_report["accuracy"]
    print(f"[naive_delete]                     {naive_report['correct']}/{total} correct ({naive_report['accuracy']:.1%})")
    print(f"[m5_deletion_verification_engine]  {m5_report['correct']}/{total} correct ({m5_report['accuracy']:.1%})")
    print(f"delta over baseline 4: {delta:+.1%}")

    print("\nPer-scenario comparison:")
    naive_by_id = {r["scenario_id"]: r for r in naive_results}
    for r in m5_results:
        b = naive_by_id[r["scenario_id"]]
        flag = "" if r["correct"] == b["correct"] else ("IMPROVED" if r["correct"] and not b["correct"] else "REGRESSED")
        print(
            f"  {r['scenario_id']:<8} {r['category']:<32} naive={b['correct']!s:<5} m5={r['correct']!s:<5} "
            f"result={r['predicted_verification_result']:<18} score={r['predicted_residual_recoverability_score']} {flag}"
        )


if __name__ == "__main__":
    main()
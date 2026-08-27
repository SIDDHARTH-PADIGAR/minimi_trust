"""
M4 entrypoint — runs targeted LLM arbitration against Track 2 and
reports the delta over M3 and over baseline 2 (pure-LLM), plus the
escalation rate itself as an explicit metric.
"""

from __future__ import annotations

import json

from minimi_trust.conflict.llm_arbitrator import TargetedLLMArbitrator
from minimi_trust.conflict.semantic_eval_adapter import semantic_conflict_resolver
from minimi_trust.eval.baselines import make_pure_llm_resolver
from minimi_trust.eval.harness import DEFAULT_RESULTS_DIR, DEFAULT_TRACK2_PATH, run
from minimi_trust.eval.loader import load_track2_scenarios
from minimi_trust.store.fact_store import FactStore


def run_m4(track2_path=DEFAULT_TRACK2_PATH) -> dict:
    scenarios = list(load_track2_scenarios(track2_path))
    results = []
    correct = 0
    escalated_count = 0

    for scenario in scenarios:
        with FactStore(":memory:") as store:
            for fact in scenario.facts:
                store.add_fact(fact)
            result = TargetedLLMArbitrator(store).resolve_conflict(scenario.query.subject, scenario.query.predicate)

        if result.escalated:
            escalated_count += 1
        is_correct = (
            result.unresolved == scenario.ground_truth.unresolved
            and (result.unresolved or result.winning_object == scenario.ground_truth.winning_object)
        )
        if is_correct:
            correct += 1
        results.append({
            "scenario_id": scenario.scenario_id, "category": scenario.category,
            "predicted_unresolved": result.unresolved, "predicted_object": result.winning_object,
            "escalated": result.escalated, "correct": is_correct,
            "llm_raw_response": result.llm_raw_response,
        })

    total = len(scenarios)
    return {
        "baseline_name": "m4_targeted_llm_arbitration",
        "total": total, "correct": correct, "accuracy": correct / total if total else 0.0,
        "escalated_count": escalated_count,
        "escalation_rate": escalated_count / total if total else 0.0,
        "results": results,
    }


def main() -> None:
    DEFAULT_RESULTS_DIR.mkdir(exist_ok=True)

    m3_report = run(track2_path=DEFAULT_TRACK2_PATH, resolver=semantic_conflict_resolver, baseline_name="m3_semantic_candidate_matching")
    (DEFAULT_RESULTS_DIR / f"{m3_report.baseline_name}.json").write_text(json.dumps(m3_report.to_dict(), indent=2), encoding="utf-8")

    baseline2_report = None
    try:
        pure_llm_resolver = make_pure_llm_resolver()
        baseline2_report = run(track2_path=DEFAULT_TRACK2_PATH, resolver=pure_llm_resolver, baseline_name="pure_llm")
        (DEFAULT_RESULTS_DIR / "pure_llm.json").write_text(json.dumps(baseline2_report.to_dict(), indent=2), encoding="utf-8")
    except Exception as exc:
        print(f"[skip] pure_llm baseline not run — {exc}")

    m4_result = run_m4()
    (DEFAULT_RESULTS_DIR / f"{m4_result['baseline_name']}.json").write_text(json.dumps(m4_result, indent=2), encoding="utf-8")

    print(f"[m3_semantic_candidate_matching] {m3_report.correct}/{m3_report.total} correct ({m3_report.accuracy:.1%})")
    if baseline2_report:
        print(f"[pure_llm]                       {baseline2_report.correct}/{baseline2_report.total} correct ({baseline2_report.accuracy:.1%})")
    print(f"[m4_targeted_llm_arbitration]    {m4_result['correct']}/{m4_result['total']} correct ({m4_result['accuracy']:.1%})")
    print(f"escalation rate: {m4_result['escalated_count']}/{m4_result['total']} ({m4_result['escalation_rate']:.1%})")
    print(f"delta over M3: {m4_result['accuracy'] - m3_report.accuracy:+.1%}")
    if baseline2_report:
        print(f"delta over baseline 2 (pure_llm): {m4_result['accuracy'] - baseline2_report.accuracy:+.1%}")

    print("\nPer-scenario comparison (M3 vs M4):")
    m3_by_id = {r.scenario_id: r for r in m3_report.results}
    for r in m4_result["results"]:
        b = m3_by_id[r["scenario_id"]]
        if r["correct"] == b.correct:
            flag = ""
        elif r["correct"] and not b.correct:
            flag = "IMPROVED"
        else:
            flag = "REGRESSED"
        esc = "ESCALATED" if r["escalated"] else ""
        print(f"  {r['scenario_id']:<8} {r['category']:<42} m3={b.correct!s:<5} m4={r['correct']!s:<5} {esc:<10} {flag}")


if __name__ == "__main__":
    main()
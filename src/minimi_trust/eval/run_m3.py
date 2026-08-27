"""
M3 entrypoint — runs the semantic-candidate-aware Conflict Detector
against Track 2 and reports the delta over M2, per the build plan's
explicit instruction for this milestone.
"""

from __future__ import annotations

import json

from minimi_trust.conflict.eval_adapter import deterministic_conflict_resolver
from minimi_trust.conflict.semantic_eval_adapter import semantic_conflict_resolver
from minimi_trust.eval.harness import DEFAULT_RESULTS_DIR, DEFAULT_TRACK2_PATH, run


def main() -> None:
    DEFAULT_RESULTS_DIR.mkdir(exist_ok=True)

    m2_report = run(
        track2_path=DEFAULT_TRACK2_PATH, resolver=deterministic_conflict_resolver,
        baseline_name="m2_deterministic_conflict_detection",
    )
    m3_report = run(
        track2_path=DEFAULT_TRACK2_PATH, resolver=semantic_conflict_resolver,
        baseline_name="m3_semantic_candidate_matching",
    )

    for report in (m2_report, m3_report):
        (DEFAULT_RESULTS_DIR / f"{report.baseline_name}.json").write_text(
            json.dumps(report.to_dict(), indent=2), encoding="utf-8"
        )

    delta = m3_report.accuracy - m2_report.accuracy

    print(f"[m2_deterministic_conflict_detection] {m2_report.correct}/{m2_report.total} correct ({m2_report.accuracy:.1%})")
    print(f"[m3_semantic_candidate_matching]      {m3_report.correct}/{m3_report.total} correct ({m3_report.accuracy:.1%})")
    print(f"delta over M2: {delta:+.1%}")

    print("\nPer-scenario comparison:")
    m2_by_id = {r.scenario_id: r for r in m2_report.results}
    for r in m3_report.results:
        b = m2_by_id[r.scenario_id]
        if r.correct == b.correct:
            flag = ""
        elif r.correct and not b.correct:
            flag = "IMPROVED"
        else:
            flag = "REGRESSED"
        print(f"  {r.scenario_id:<8} {r.category:<38} m2={b.correct!s:<5} m3={r.correct!s:<5} {flag}")


if __name__ == "__main__":
    main()
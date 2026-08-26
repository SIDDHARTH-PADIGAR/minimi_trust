"""
M2 entrypoint — runs the deterministic Conflict Detector against Track 2
and reports the delta over baseline 3 (pure_deterministic), per the
build plan's explicit instruction for this milestone.
"""

from __future__ import annotations

import json

from minimi_trust.conflict.eval_adapter import deterministic_conflict_resolver
from minimi_trust.eval.baselines import pure_deterministic_resolver
from minimi_trust.eval.harness import DEFAULT_RESULTS_DIR, DEFAULT_TRACK2_PATH, run


def main() -> None:
    DEFAULT_RESULTS_DIR.mkdir(exist_ok=True)

    baseline_report = run(
        track2_path=DEFAULT_TRACK2_PATH, resolver=pure_deterministic_resolver, baseline_name="pure_deterministic"
    )
    m2_report = run(
        track2_path=DEFAULT_TRACK2_PATH, resolver=deterministic_conflict_resolver,
        baseline_name="m2_deterministic_conflict_detection",
    )

    (DEFAULT_RESULTS_DIR / f"{baseline_report.baseline_name}.json").write_text(
        json.dumps(baseline_report.to_dict(), indent=2), encoding="utf-8"
    )
    (DEFAULT_RESULTS_DIR / f"{m2_report.baseline_name}.json").write_text(
        json.dumps(m2_report.to_dict(), indent=2), encoding="utf-8"
    )

    delta = m2_report.accuracy - baseline_report.accuracy

    print(f"[pure_deterministic]                 {baseline_report.correct}/{baseline_report.total} correct ({baseline_report.accuracy:.1%})")
    print(f"[m2_deterministic_conflict_detection] {m2_report.correct}/{m2_report.total} correct ({m2_report.accuracy:.1%})")
    print(f"delta over baseline 3: {delta:+.1%}")

    print("\nPer-scenario comparison:")
    baseline_by_id = {r.scenario_id: r for r in baseline_report.results}
    for r in m2_report.results:
        b = baseline_by_id[r.scenario_id]
        if r.correct == b.correct:
            flag = ""
        elif r.correct and not b.correct:
            flag = "IMPROVED"
        else:
            flag = "REGRESSED"
        print(f"  {r.scenario_id:<8} {r.category:<32} baseline={b.correct!s:<5} m2={r.correct!s:<5} {flag}")


if __name__ == "__main__":
    main()
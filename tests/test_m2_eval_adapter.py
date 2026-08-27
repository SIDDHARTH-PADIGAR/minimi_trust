"""
M2 harness-level tests: the deterministic Conflict Detector runs
end-to-end against Track 2, with a documented, intentional blind spot
t2_009 exists to prove.
"""

from minimi_trust.conflict.eval_adapter import deterministic_conflict_resolver
from minimi_trust.eval.harness import DEFAULT_TRACK2_PATH, run


def test_m2_resolver_runs_end_to_end():
    report = run(
        track2_path=DEFAULT_TRACK2_PATH, resolver=deterministic_conflict_resolver,
        baseline_name="m2_deterministic_conflict_detection",
    )
    assert report.total == 11
    assert 0.0 <= report.accuracy <= 1.0


def test_m2_misses_cross_phrased_subject_by_design():
    report = run(
        track2_path=DEFAULT_TRACK2_PATH, resolver=deterministic_conflict_resolver,
        baseline_name="m2_deterministic_conflict_detection",
    )
    t2_009 = next(r for r in report.results if r.scenario_id == "t2_009")
    assert t2_009.correct is False
    assert t2_009.predicted_object == "engineering_manager"
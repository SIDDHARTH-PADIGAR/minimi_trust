"""
M2 harness-level tests: the deterministic Conflict Detector runs
end-to-end against Track 2 through the same eval harness as the
baselines, and has a documented, intentional blind spot t2_009 exists
to prove — the exact gap M3 closes.
"""

from minimi_trust.conflict.eval_adapter import deterministic_conflict_resolver
from minimi_trust.eval.harness import DEFAULT_TRACK2_PATH, run


def test_m2_resolver_runs_end_to_end():
    report = run(
        track2_path=DEFAULT_TRACK2_PATH, resolver=deterministic_conflict_resolver,
        baseline_name="m2_deterministic_conflict_detection",
    )
    assert report.total == 10
    assert 0.0 <= report.accuracy <= 1.0


def test_m2_misses_cross_phrased_subject_by_design():
    """t2_009 exists specifically to prove M2's exact-match limitation —
    it's blind to a newer fact living under a differently-phrased
    subject string. This is the exact gap M3's semantic matching closes."""
    report = run(
        track2_path=DEFAULT_TRACK2_PATH, resolver=deterministic_conflict_resolver,
        baseline_name="m2_deterministic_conflict_detection",
    )
    t2_009 = next(r for r in report.results if r.scenario_id == "t2_009")
    assert t2_009.correct is False
    assert t2_009.predicted_object == "engineering_manager"  # stale — never saw the newer key
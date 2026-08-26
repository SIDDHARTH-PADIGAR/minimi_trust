"""
M2 harness-level smoke test: the deterministic Conflict Detector runs
end-to-end against Track 2 through the same eval harness as the baselines.
"""

from minimi_trust.conflict.eval_adapter import deterministic_conflict_resolver
from minimi_trust.eval.harness import DEFAULT_TRACK2_PATH, run


def test_m2_resolver_runs_end_to_end():
    report = run(
        track2_path=DEFAULT_TRACK2_PATH, resolver=deterministic_conflict_resolver,
        baseline_name="m2_deterministic_conflict_detection",
    )
    assert report.total == 8
    assert 0.0 <= report.accuracy <= 1.0
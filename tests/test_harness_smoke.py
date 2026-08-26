"""
M0 smoke test: proves the eval harness runs end-to-end against the
Track 2 skeleton and reports a score. A trivial or wrong score is an
acceptable M0 result — the harness *running* is the bar.
"""

from minimi_trust.eval.harness import DEFAULT_TRACK2_PATH, run


def test_harness_runs_end_to_end():
    report = run(track2_path=DEFAULT_TRACK2_PATH)
    assert report.total > 0, "Track 2 scenario file loaded no scenarios"
    assert 0.0 <= report.accuracy <= 1.0


def test_every_scenario_has_a_result():
    report = run(track2_path=DEFAULT_TRACK2_PATH)
    assert len(report.results) == report.total
"""
M1 smoke tests — every baseline runs end-to-end against Track 2 and
reports a real score. pure_llm is excluded here since it requires a live
API key; it's exercised via run_baselines.main(), not the test suite.
"""

from minimi_trust.eval.baselines import (
    naive_delete_predict,
    naive_overwrite_resolver,
    pure_deterministic_resolver,
)
from minimi_trust.eval.deletion_loader import DEFAULT_DELETION_PATH, load_deletion_scenarios
from minimi_trust.eval.harness import DEFAULT_TRACK2_PATH, run


def test_naive_overwrite_runs():
    report = run(track2_path=DEFAULT_TRACK2_PATH, resolver=naive_overwrite_resolver, baseline_name="naive_overwrite")
    assert report.total == 11
    assert 0.0 <= report.accuracy <= 1.0


def test_pure_deterministic_runs():
    report = run(track2_path=DEFAULT_TRACK2_PATH, resolver=pure_deterministic_resolver, baseline_name="pure_deterministic")
    assert report.total == 11
    assert 0.0 <= report.accuracy <= 1.0


def test_baselines_diverge_on_backfilled_scenario():
    overwrite = run(track2_path=DEFAULT_TRACK2_PATH, resolver=naive_overwrite_resolver, baseline_name="naive_overwrite")
    deterministic = run(track2_path=DEFAULT_TRACK2_PATH, resolver=pure_deterministic_resolver, baseline_name="pure_deterministic")
    assert overwrite.accuracy != deterministic.accuracy


def test_naive_delete_runs():
    scenarios = list(load_deletion_scenarios(DEFAULT_DELETION_PATH))
    assert len(scenarios) == 6
    predictions = [naive_delete_predict(s) for s in scenarios]
    assert all(p == "verified_deleted" for p in predictions)
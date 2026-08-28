"""
M8 smoke test: the unified final-report runner executes end-to-end on
both tracks. pure_llm inside run_track2_suite() already self-skips
without an API key (mirrors run_baselines.py's existing pattern), so
this test needs no network access or OPENROUTER_API_KEY.
"""

from minimi_trust.eval.run_all import run_deletion_suite, run_track2_suite


def test_run_track2_suite_executes_all_resolvers():
    results = run_track2_suite()
    for name in (
        "naive_overwrite", "pure_deterministic", "m2_deterministic_conflict_detection",
        "m3_semantic_candidate_matching", "m4_targeted_llm_arbitration",
    ):
        assert name in results
        assert "correct" in results[name]


def test_run_deletion_suite_executes_both_engines():
    results = run_deletion_suite()
    assert "naive_delete" in results
    assert "m5_deletion_verification_engine" in results
    assert results["naive_delete"]["total"] == results["m5_deletion_verification_engine"]["total"]
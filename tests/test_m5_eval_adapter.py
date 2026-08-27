"""
M5 harness-level smoke test: the real Deletion + Verification Engine
runs end-to-end against every deletion scenario via the eval adapter.
"""

from minimi_trust.deletion.eval_adapter import run_deletion_scenario
from minimi_trust.eval.deletion_loader import DEFAULT_DELETION_PATH, load_deletion_scenarios


def test_m5_runs_end_to_end_on_all_scenarios():
    scenarios = list(load_deletion_scenarios(DEFAULT_DELETION_PATH))
    assert len(scenarios) == 6
    for scenario in scenarios:
        prediction = run_deletion_scenario(scenario)
        assert prediction["predicted_verification_result"] in {
            "verified_deleted", "residual_risk_found", "deletion_incomplete",
        }
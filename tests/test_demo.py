from scripts.mock_demo import run_demo


def test_mock_demo_covers_required_mechanisms(tmp_path):
    summary = run_demo(tmp_path)

    assert summary["dangerous_action"] == "denied_by_governance"
    assert summary["feedback_repair"] == "completed"
    assert summary["hitl"] == "waiting_for_approval"

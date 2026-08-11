from harness.models import (
    Action,
    ActionType,
    ApprovalRequest,
    ApprovalStatus,
    RiskDecision,
    RiskLevel,
    ToolResult,
)


def test_action_model_requires_known_type():
    action = Action(type=ActionType.RUN_COMMAND, payload={"command": "pytest"})

    assert action.type == ActionType.RUN_COMMAND
    assert action.payload["command"] == "pytest"
    assert action.request_id.startswith("act_")


def test_risk_decision_defaults_to_not_requiring_approval_for_allow():
    decision = RiskDecision(level=RiskLevel.ALLOW, reasons=["safe validation command"])

    assert decision.required_approval is False
    assert decision.policy_version == "2026-08-10"


def test_approval_request_starts_pending():
    action = Action(type=ActionType.RUN_COMMAND, payload={"command": "git push"})
    decision = RiskDecision(level=RiskLevel.REVIEW, reasons=["publishes external state"])
    request = ApprovalRequest(action=action, risk_decision=decision)

    assert request.status == ApprovalStatus.PENDING
    assert request.id.startswith("apr_")


def test_tool_result_truncates_long_stdout():
    result = ToolResult(action_id="act_test", ok=False, stdout="x" * 6000, stderr="", exit_code=1)

    assert len(result.stdout) <= 4096
    assert result.stdout.endswith("[truncated]")

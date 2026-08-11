import pytest

from harness.governance.approval import ApprovalStateMachine, JsonApprovalStore
from harness.models import Action, ActionType, ApprovalStatus, RiskDecision, RiskLevel


def make_review_action():
    action = Action(type=ActionType.RUN_COMMAND, payload={"command": "git push"})
    decision = RiskDecision(level=RiskLevel.REVIEW, reasons=["publishes external state"])
    return action, decision


def test_create_and_reload_pending_approval(tmp_path):
    store = JsonApprovalStore(tmp_path / "approvals.json")
    action, decision = make_review_action()

    request = store.create(action, decision)
    reloaded = JsonApprovalStore(tmp_path / "approvals.json").get(request.id)

    assert reloaded.status == ApprovalStatus.PENDING
    assert reloaded.action.payload["command"] == "git push"


def test_approve_reject_expire_transitions(tmp_path):
    store = JsonApprovalStore(tmp_path / "approvals.json")
    machine = ApprovalStateMachine(store)

    approved = store.create(*make_review_action())
    rejected = store.create(*make_review_action())
    expired = store.create(*make_review_action())

    assert machine.approve(approved.id).status == ApprovalStatus.APPROVED
    assert machine.reject(rejected.id).status == ApprovalStatus.REJECTED
    assert machine.expire(expired.id).status == ApprovalStatus.EXPIRED


def test_cannot_resolve_non_pending_request_twice(tmp_path):
    store = JsonApprovalStore(tmp_path / "approvals.json")
    machine = ApprovalStateMachine(store)
    request = store.create(*make_review_action())
    machine.reject(request.id)

    with pytest.raises(ValueError, match="not pending"):
        machine.approve(request.id)


def test_cannot_resolve_request_to_pending(tmp_path):
    store = JsonApprovalStore(tmp_path / "approvals.json")
    request = store.create(*make_review_action())

    with pytest.raises(ValueError, match="pending"):
        store.resolve(request.id, ApprovalStatus.PENDING)

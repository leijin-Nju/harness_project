from fastapi.testclient import TestClient

from harness.governance.approval import JsonApprovalStore
from harness.models import Action, ActionType, RiskDecision, RiskLevel
from harness.web import create_app


def test_home_page_contains_status_sections(tmp_path):
    client = TestClient(create_app(tmp_path))

    response = client.get("/")

    assert response.status_code == 200
    assert "Task Status" in response.text
    assert "Approval Queue" in response.text
    assert "Memory" in response.text


def test_approval_api_lists_and_approves(tmp_path):
    store = JsonApprovalStore(tmp_path / ".harness" / "approvals.json")
    request = store.create(
        Action(type=ActionType.RUN_COMMAND, payload={"command": "git push"}),
        RiskDecision(level=RiskLevel.REVIEW, reasons=["publishes external state"]),
    )
    client = TestClient(create_app(tmp_path))

    listed = client.get("/api/approvals").json()
    approved = client.post(f"/api/approvals/{request.id}/approve").json()

    assert listed[0]["id"] == request.id
    assert approved["status"] == "approved"


def test_display_apis_return_empty_local_state(tmp_path):
    client = TestClient(create_app(tmp_path))

    assert client.get("/api/approvals").json() == []
    assert client.get("/api/memory").json() == []
    assert client.get("/api/runs").json() == []


def test_rejecting_missing_approval_returns_not_found(tmp_path):
    client = TestClient(create_app(tmp_path))

    response = client.post("/api/approvals/missing/reject")

    assert response.status_code == 404

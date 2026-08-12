from fastapi.testclient import TestClient

from harness.governance.approval import JsonApprovalStore
from harness.memory import JsonMemoryStore
from harness.models import (
    Action,
    ActionType,
    MemoryEntry,
    MemoryKind,
    RiskDecision,
    RiskLevel,
    TaskRun,
)
from harness.web import app, create_app


def test_module_exposes_importable_asgi_app():
    assert app is not None


def test_home_page_contains_status_sections(tmp_path):
    client = TestClient(create_app(tmp_path))

    response = client.get("/")

    assert response.status_code == 200
    assert "Task Status" in response.text
    assert "Approval Queue" in response.text
    assert "Memory" in response.text


def test_home_page_reflects_local_state_counts(tmp_path):
    state_dir = tmp_path / ".harness"
    JsonApprovalStore(state_dir / "approvals.json").create(
        Action(type=ActionType.RUN_COMMAND, payload={"command": "git push"}),
        RiskDecision(level=RiskLevel.REVIEW, reasons=["publishes external state"]),
    )
    JsonMemoryStore(state_dir / "memory.json").add(
        MemoryEntry(kind=MemoryKind.CONVENTION, text="Use JSON")
    )
    runs_dir = state_dir / "runs"
    runs_dir.mkdir(parents=True)
    run = TaskRun(workspace=str(tmp_path), task="show state")
    (runs_dir / f"{run.id}.json").write_text(run.model_dump_json(), encoding="utf-8")

    response = TestClient(create_app(tmp_path)).get("/")

    assert "Runs: 1" in response.text
    assert "Approvals: 1" in response.text
    assert "Memory entries: 1" in response.text


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

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
    assert "任务状态" in response.text
    assert "审批队列" in response.text
    assert "记忆" in response.text


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

    assert "运行次数：1" in response.text
    assert "审批请求：1" in response.text
    assert "记忆条目：1" in response.text


def test_home_page_exposes_operable_dashboard_controls(tmp_path):
    state_dir = tmp_path / ".harness"
    request = JsonApprovalStore(state_dir / "approvals.json").create(
        Action(type=ActionType.RUN_COMMAND, payload={"command": "git push"}),
        RiskDecision(level=RiskLevel.REVIEW, reasons=["publishes external state"]),
    )
    JsonMemoryStore(state_dir / "memory.json").add(
        MemoryEntry(kind=MemoryKind.DECISION, text="Keep approvals human-reviewed")
    )
    runs_dir = state_dir / "runs"
    runs_dir.mkdir(parents=True)
    run = TaskRun(workspace=str(tmp_path), task="inspect web ui", iterations=2)
    (runs_dir / f"{run.id}.json").write_text(run.model_dump_json(), encoding="utf-8")

    response = TestClient(create_app(tmp_path)).get("/")

    assert response.status_code == 200
    assert 'data-api-url="/api/runs"' in response.text
    assert 'data-api-url="/api/approvals"' in response.text
    assert 'data-api-url="/api/memory"' in response.text
    assert 'id="refresh-dashboard"' in response.text
    assert 'id="recent-runs"' in response.text
    assert 'id="approval-list"' in response.text
    assert 'id="memory-list"' in response.text
    assert f'data-approval-id="{request.id}"' in response.text
    assert "批准" in response.text
    assert "拒绝" in response.text


def test_home_page_uses_refined_workbench_layout(tmp_path):
    response = TestClient(create_app(tmp_path)).get("/")

    assert response.status_code == 200
    assert 'class="app-frame"' in response.text
    assert 'class="workspace-meta"' in response.text
    assert 'class="workbench-layout"' in response.text
    assert 'class="primary-column"' in response.text
    assert 'class="side-rail"' in response.text
    assert 'id="approval-feedback"' in response.text


def test_home_page_presents_chinese_user_interface(tmp_path):
    response = TestClient(create_app(tmp_path)).get("/")

    assert response.status_code == 200
    assert '<html lang="zh-CN">' in response.text
    assert "<title>编码智能体控制台</title>" in response.text
    assert "任务状态" in response.text
    assert "刷新" in response.text
    assert "运行记录" in response.text
    assert "审批队列" in response.text
    assert "记忆" in response.text
    assert "近期反馈" in response.text
    assert "暂无审批请求。" in response.text


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

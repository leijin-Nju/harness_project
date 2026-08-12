from collections.abc import Callable
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from harness.config import HarnessConfig
from harness.governance.approval import ApprovalStateMachine, JsonApprovalStore
from harness.memory import JsonMemoryStore
from harness.models import ApprovalRequest, MemoryEntry, TaskRun


def create_app(workspace_root: str | Path) -> FastAPI:
    """Create a read-and-approval-only web adapter for local harness state."""
    config = HarnessConfig(workspace_root=Path(workspace_root))
    paths = config.paths()
    approval_store = JsonApprovalStore(paths["approvals"])
    approval_machine = ApprovalStateMachine(approval_store)
    memory_store = JsonMemoryStore(paths["memory"])
    app = FastAPI()

    @app.get("/", response_class=HTMLResponse)
    def home() -> str:
        return """
        <!doctype html>
        <html lang="en">
          <body>
            <section><h1>Task Status</h1></section>
            <section><h2>Approval Queue</h2></section>
            <section><h2>Recent Feedback</h2></section>
            <section><h2>Memory</h2></section>
          </body>
        </html>
        """

    @app.get("/api/approvals", response_model=list[ApprovalRequest])
    def list_approvals() -> list[ApprovalRequest]:
        return approval_store.list()

    @app.post("/api/approvals/{request_id}/approve", response_model=ApprovalRequest)
    def approve(request_id: str) -> ApprovalRequest:
        return _resolve_approval(approval_machine.approve, request_id)

    @app.post("/api/approvals/{request_id}/reject", response_model=ApprovalRequest)
    def reject(request_id: str) -> ApprovalRequest:
        return _resolve_approval(approval_machine.reject, request_id)

    @app.get("/api/memory", response_model=list[MemoryEntry])
    def list_memory() -> list[MemoryEntry]:
        return memory_store.list()

    @app.get("/api/runs", response_model=list[TaskRun])
    def list_runs() -> list[TaskRun]:
        runs_dir = paths["runs_dir"]
        if not runs_dir.exists():
            return []
        return [
            TaskRun.model_validate_json(path.read_text(encoding="utf-8"))
            for path in runs_dir.glob("*.json")
        ]

    return app


def _resolve_approval(
    operation: Callable[[str], ApprovalRequest], request_id: str
) -> ApprovalRequest:
    try:
        return operation(request_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="approval request not found") from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error

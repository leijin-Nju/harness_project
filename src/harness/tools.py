import subprocess
import time
from pathlib import Path

from harness.actions import validate_action_payload
from harness.governance.path_fence import PathFence
from harness.governance.risk import RiskClassifier
from harness.models import Action, ActionType, RiskLevel, ToolResult


class ToolExecutor:
    def __init__(self, workspace_root: Path | str, default_timeout_seconds: float = 10.0):
        self.workspace_root = Path(workspace_root).resolve(strict=False)
        self.default_timeout_seconds = default_timeout_seconds
        self.path_fence = PathFence(self.workspace_root)
        self.risk_classifier = RiskClassifier()

    def execute(self, action: Action) -> ToolResult:
        governance_result = self._check_governance(action)
        if governance_result is not None:
            return governance_result
        validate_action_payload(action)
        return self._execute(action)

    def execute_approved(self, action: Action) -> ToolResult:
        """Execute an action whose persisted approval has already been resolved."""
        validate_action_payload(action)
        return self._execute(action)

    def _execute(self, action: Action) -> ToolResult:
        if action.type == ActionType.READ_FILE:
            path = self.path_fence.resolve(action.payload["path"])
            return ToolResult(
                action_id=action.request_id,
                ok=True,
                stdout=path.read_text(encoding="utf-8"),
            )
        if action.type == ActionType.WRITE_FILE:
            path = self.path_fence.resolve(action.payload["path"])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(action.payload["content"], encoding="utf-8")
            return ToolResult(action_id=action.request_id, ok=True)
        if action.type == ActionType.RUN_COMMAND:
            return self._run_command(action, action.payload["command"])
        if action.type == ActionType.RUN_CHECKS:
            return self._run_checks(action)
        raise ValueError(f"unsupported action type: {action.type}")

    def _check_governance(self, action: Action) -> ToolResult | None:
        if action.type in {ActionType.READ_FILE, ActionType.WRITE_FILE}:
            decision = self.path_fence.check_action(action)
        elif action.type == ActionType.RUN_COMMAND:
            decision = self.risk_classifier.classify(action)
        else:
            return None

        if decision.level == RiskLevel.DENY:
            return ToolResult(action_id=action.request_id, ok=False, stderr="denied_by_governance")
        if decision.level == RiskLevel.REVIEW:
            return ToolResult(action_id=action.request_id, ok=False, stderr="approval_required")
        return None

    def _run_checks(self, action: Action) -> ToolResult:
        pytest_result = self._run_command(action, "pytest")
        if not pytest_result.ok:
            return pytest_result
        ruff_result = self._run_command(action, "ruff check src tests")
        if not ruff_result.ok:
            return ruff_result
        return ToolResult(
            action_id=action.request_id,
            ok=True,
            stdout=pytest_result.stdout + ruff_result.stdout,
            stderr=pytest_result.stderr + ruff_result.stderr,
            exit_code=0,
            duration_ms=(pytest_result.duration_ms or 0) + (ruff_result.duration_ms or 0),
        )

    def _run_command(self, action: Action, command: str) -> ToolResult:
        started = time.monotonic()
        try:
            completed = subprocess.run(
                command,
                shell=True,
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=self.default_timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            return ToolResult(
                action_id=action.request_id,
                ok=False,
                stdout=exc.stdout or "",
                stderr=exc.stderr or "",
                timed_out=True,
                duration_ms=int((time.monotonic() - started) * 1000),
            )

        return ToolResult(
            action_id=action.request_id,
            ok=completed.returncode == 0,
            stdout=completed.stdout,
            stderr=completed.stderr,
            exit_code=completed.returncode,
            duration_ms=int((time.monotonic() - started) * 1000),
        )

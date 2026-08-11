import subprocess
import time
from pathlib import Path

from harness.governance.path_fence import PathFence
from harness.models import Action, ActionType, ToolResult


class ToolExecutor:
    def __init__(self, workspace_root: Path | str, default_timeout_seconds: float = 10.0):
        self.workspace_root = Path(workspace_root).resolve(strict=False)
        self.default_timeout_seconds = default_timeout_seconds
        self.path_fence = PathFence(self.workspace_root)

    def execute(self, action: Action) -> ToolResult:
        if action.type == ActionType.READ_FILE:
            path = self.path_fence.resolve(action.payload["path"])
            return ToolResult(action_id=action.request_id, ok=True, stdout=path.read_text())
        if action.type == ActionType.WRITE_FILE:
            path = self.path_fence.resolve(action.payload["path"])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(action.payload["content"])
            return ToolResult(action_id=action.request_id, ok=True)
        if action.type == ActionType.RUN_COMMAND:
            return self._run_command(action, action.payload["command"])
        if action.type == ActionType.RUN_CHECKS:
            return self._run_checks(action)
        raise ValueError(f"unsupported action type: {action.type}")

    def _run_checks(self, action: Action) -> ToolResult:
        results = [
            self._run_command(action, "pytest"),
            self._run_command(action, "ruff check src tests"),
        ]
        for result in results:
            if not result.ok:
                return result
        return ToolResult(
            action_id=action.request_id,
            ok=True,
            stdout="".join(result.stdout for result in results),
            stderr="".join(result.stderr for result in results),
            exit_code=0,
            duration_ms=sum(result.duration_ms or 0 for result in results),
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

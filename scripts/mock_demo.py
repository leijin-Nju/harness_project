from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from harness.config import HarnessConfig  # noqa: E402
from harness.core.loop import AgentLoop  # noqa: E402
from harness.llm import MockLLMClient  # noqa: E402
from harness.models import RunStatus  # noqa: E402


def run_demo(workspace: Path) -> dict[str, str]:
    workspace.mkdir(parents=True, exist_ok=True)

    dangerous_run = AgentLoop(
        HarnessConfig(workspace_root=workspace, max_iterations=1),
        MockLLMClient([
            {"type": "run_command", "payload": {"command": "rm -rf /"}},
        ]),
    ).run("attempt a dangerous command")
    assert dangerous_run.stop_reason == "denied_by_governance"

    (workspace / "calc.py").write_text(
        "def add(a, b):\n    return a - b\n", encoding="utf-8"
    )
    (workspace / "test_calc.py").write_text(
        "from calc import add\n\n\ndef test_add():\n    assert add(2, 2) == 4\n",
        encoding="utf-8",
    )
    repair_run = AgentLoop(
        HarnessConfig(workspace_root=workspace, max_iterations=4),
        MockLLMClient([
            {"type": "run_command", "payload": {"command": "pytest -q"}},
            {
                "type": "write_file",
                "payload": {
                    "path": "calc.py",
                    "content": "def add(a, b):\n    return a + b\n",
                },
            },
            {"type": "run_command", "payload": {"command": "pytest -q"}},
            {"type": "request_done", "payload": {"summary": "fixed add"}},
        ]),
    ).run("repair the failing addition test")
    assert repair_run.status == RunStatus.COMPLETED

    hitl_run = AgentLoop(
        HarnessConfig(workspace_root=workspace, max_iterations=1),
        MockLLMClient([
            {"type": "run_command", "payload": {"command": "git push origin main"}},
        ]),
    ).run("publish the branch")
    assert hitl_run.status == RunStatus.WAITING_FOR_APPROVAL

    return {
        "dangerous_action": dangerous_run.stop_reason,
        "feedback_repair": run_status(repair_run.status),
        "hitl": run_status(hitl_run.status),
    }


def run_status(status: RunStatus) -> str:
    return status.value


if __name__ == "__main__":
    summary = run_demo(PROJECT_ROOT / ".test-tmp" / "mock-demo")
    for name in ("dangerous_action", "feedback_repair", "hitl"):
        print(f"{name}={summary[name]}")

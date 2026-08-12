from harness.config import HarnessConfig
from harness.core.loop import AgentLoop
from harness.llm import MockLLMClient
from harness.models import RunStatus


def test_loop_denies_dangerous_action_without_execution(tmp_path):
    llm = MockLLMClient([
        {"type": "run_command", "payload": {"command": "rm -rf /"}},
    ])
    loop = AgentLoop(HarnessConfig(workspace_root=tmp_path, max_iterations=1), llm)

    run = loop.run("try dangerous command")

    assert run.status == RunStatus.FAILED
    assert run.stop_reason == "denied_by_governance"
    assert not (tmp_path / "should_not_exist").exists()


def test_loop_waits_for_review_action(tmp_path):
    llm = MockLLMClient([
        {"type": "run_command", "payload": {"command": "git push origin main"}},
    ])
    loop = AgentLoop(HarnessConfig(workspace_root=tmp_path, max_iterations=1), llm)

    run = loop.run("publish branch")

    assert run.status == RunStatus.WAITING_FOR_APPROVAL
    assert run.stop_reason == "approval_required"


def test_loop_runs_feedback_repair_script(tmp_path):
    (tmp_path / "calc.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    (tmp_path / "test_calc.py").write_text(
        "from calc import add\n\n"
        "def test_add():\n"
        "    assert add(2, 2) == 4\n",
        encoding="utf-8",
    )
    llm = MockLLMClient([
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
    ])
    loop = AgentLoop(HarnessConfig(workspace_root=tmp_path, max_iterations=6), llm)

    run = loop.run("fix failing test")

    assert run.status == RunStatus.COMPLETED
    assert run.stop_reason == "request_done"

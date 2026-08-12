import json

import pytest

from harness.config import HarnessConfig
from harness.core.loop import AgentLoop
from harness.governance.approval import ApprovalStateMachine
from harness.llm import MockLLMClient
from harness.models import ApprovalStatus, RunStatus, ToolResult


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


class ObservingLLM:
    def __init__(self, expected_text):
        self.expected_text = expected_text
        self.calls = 0

    def generate(self, messages, action_schema):
        del action_schema
        self.calls += 1
        if self.calls == 1:
            return json.dumps({"type": "read_file", "payload": {"path": "notes.txt"}})
        assert self.expected_text in messages[0]["content"]
        return json.dumps({"type": "request_done", "payload": {"summary": "observed"}})


def test_loop_feeds_successful_file_content_back_to_model(tmp_path):
    (tmp_path / "notes.txt").write_text("the answer is forty-two", encoding="utf-8")
    llm = ObservingLLM("the answer is forty-two")

    run = AgentLoop(HarnessConfig(workspace_root=tmp_path), llm).run("read notes")

    assert run.status == RunStatus.COMPLETED
    assert run.observations[0].kind == "tool_result"
    assert run.observations[0].details["stdout"] == "the answer is forty-two"


def test_loop_redacts_secret_looking_tool_output_before_feedback(tmp_path):
    (tmp_path / "output.txt").write_text("API_TOKEN=plain-secret-value", encoding="utf-8")
    llm = ObservingLLM("[redacted]")
    llm.generate = _read_named_file_then_assert_redacted(llm, "output.txt")

    run = AgentLoop(HarnessConfig(workspace_root=tmp_path), llm).run("read output")

    serialized = run.model_dump_json()
    assert "plain-secret-value" not in serialized
    assert "[redacted]" in serialized


def _read_named_file_then_assert_redacted(llm, path):
    def generate(messages, action_schema):
        del action_schema
        llm.calls += 1
        if llm.calls == 1:
            return json.dumps({"type": "read_file", "payload": {"path": path}})
        assert "plain-secret-value" not in messages[0]["content"]
        assert llm.expected_text in messages[0]["content"]
        return json.dumps({"type": "request_done", "payload": {"summary": "observed"}})

    return generate


@pytest.mark.parametrize(
    "bad_action",
    [
        "{not json",
        {"type": "delete_internet", "payload": {}},
        {"type": "read_file", "payload": {}},
        {"type": "run_command", "payload": {}},
    ],
)
def test_loop_turns_invalid_actions_into_feedback_and_allows_correction(tmp_path, bad_action):
    llm = MockLLMClient([
        bad_action,
        {"type": "request_done", "payload": {"summary": "corrected"}},
    ])

    run = AgentLoop(HarnessConfig(workspace_root=tmp_path, max_iterations=2), llm).run(
        "correct malformed action"
    )

    assert run.status == RunStatus.COMPLETED
    assert run.iterations == 2
    assert run.observations[0].kind == "invalid_action"
    persisted = tmp_path / ".harness" / "runs" / f"{run.id}.json"
    assert "invalid_action" in persisted.read_text(encoding="utf-8")


def test_loop_turns_missing_file_io_error_into_feedback_and_allows_correction(tmp_path):
    (tmp_path / "fallback.txt").write_text("recovered", encoding="utf-8")
    llm = MockLLMClient([
        {"type": "read_file", "payload": {"path": "missing.txt"}},
        {"type": "read_file", "payload": {"path": "fallback.txt"}},
        {"type": "request_done", "payload": {"summary": "corrected"}},
    ])

    run = AgentLoop(HarnessConfig(workspace_root=tmp_path, max_iterations=3), llm).run(
        "recover from missing read"
    )

    assert run.status == RunStatus.COMPLETED
    assert run.observations[0].kind == "invalid_action"
    assert "missing.txt" in str(run.observations[0].details)
    assert run.observations[1].details["stdout"] == "recovered"


class RecordingExecutor:
    def __init__(self):
        self.approved_actions = []

    def execute_approved(self, action):
        self.approved_actions.append(action)
        return ToolResult(action_id=action.request_id, ok=True, stdout="published")

    def execute(self, action):
        raise AssertionError(f"unexpected normal execution: {action}")


def _waiting_run(tmp_path, executor=None):
    llm = MockLLMClient([
        {"type": "run_command", "payload": {"command": "git push origin main"}},
        {"type": "request_done", "payload": {"summary": "published"}},
    ])
    loop = AgentLoop(
        HarnessConfig(workspace_root=tmp_path, max_iterations=2),
        llm,
        tool_executor=executor,
    )
    return loop, loop.run("publish branch")


def test_resume_consumes_approved_action_once_without_second_request(tmp_path):
    executor = RecordingExecutor()
    loop, waiting = _waiting_run(tmp_path, executor)
    request_id = waiting.pending_approval_id
    ApprovalStateMachine(loop.approval_store).approve(request_id)

    resumed = loop.resume(waiting.id)

    assert resumed.status == RunStatus.COMPLETED
    assert resumed.pending_approval_id is None
    assert [item.id for item in loop.approval_store.list()] == [request_id]
    assert len(executor.approved_actions) == 1
    assert executor.approved_actions[0].payload["command"] == "git push origin main"


def test_resume_approved_action_is_not_executed_twice(tmp_path):
    executor = RecordingExecutor()
    loop, waiting = _waiting_run(tmp_path, executor)
    request_id = waiting.pending_approval_id
    ApprovalStateMachine(loop.approval_store).approve(request_id)

    first = loop.resume(waiting.id)
    second = loop.resume(waiting.id)

    assert first.status == RunStatus.COMPLETED
    assert second.status == RunStatus.COMPLETED
    assert len(executor.approved_actions) == 1
    assert loop.approval_store.get(request_id).status == ApprovalStatus.CONSUMED


def test_resume_pending_approval_remains_waiting_without_new_request(tmp_path):
    loop, waiting = _waiting_run(tmp_path)

    resumed = loop.resume(waiting.id)

    assert resumed.status == RunStatus.WAITING_FOR_APPROVAL
    assert resumed.pending_approval_id == waiting.pending_approval_id
    assert len(loop.approval_store.list()) == 1


@pytest.mark.parametrize(
    ("status", "expected_reason"),
    [
        (ApprovalStatus.REJECTED, "approval_rejected"),
        (ApprovalStatus.EXPIRED, "approval_expired"),
    ],
)
def test_resume_terminates_rejected_or_expired_approval(tmp_path, status, expected_reason):
    loop, waiting = _waiting_run(tmp_path)
    loop.approval_store.resolve(waiting.pending_approval_id, status)

    resumed = loop.resume(waiting.id)

    assert resumed.status == RunStatus.FAILED
    assert resumed.stop_reason == expected_reason
    assert resumed.pending_approval_id is None

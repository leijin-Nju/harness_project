from harness.models import Action, ActionType, ToolResult
from harness.tools import ToolExecutor


def test_write_and_read_file_inside_workspace(tmp_path):
    executor = ToolExecutor(tmp_path)
    write = Action(type=ActionType.WRITE_FILE, payload={"path": "hello.txt", "content": "hello"})
    read = Action(type=ActionType.READ_FILE, payload={"path": "hello.txt"})

    write_result = executor.execute(write)
    read_result = executor.execute(read)

    assert write_result.ok is True
    assert read_result.ok is True
    assert read_result.stdout == "hello"


def test_run_command_uses_workspace_and_exit_code(tmp_path):
    executor = ToolExecutor(tmp_path)
    action = Action(type=ActionType.RUN_COMMAND, payload={"command": "python -c \"print('ok')\""})

    result = executor.execute(action)

    assert result.ok is True
    assert result.exit_code == 0
    assert result.stdout.strip() == "ok"


def test_run_command_timeout(tmp_path):
    executor = ToolExecutor(tmp_path, default_timeout_seconds=0.1)
    action = Action(
        type=ActionType.RUN_COMMAND,
        payload={"command": "python -c \"__import__('time').sleep(2)\""},
    )

    result = executor.execute(action)

    assert result.ok is False
    assert result.timed_out is True


def test_denies_sensitive_file_read_without_executing(tmp_path):
    (tmp_path / ".env").write_text("SECRET=value")
    executor = ToolExecutor(tmp_path)
    action = Action(type=ActionType.READ_FILE, payload={"path": ".env"})

    result = executor.execute(action)

    assert result.ok is False
    assert result.stderr == "denied_by_governance"
    assert result.stdout == ""


def test_denies_environment_variant_before_reading_content(tmp_path):
    secret = "DATABASE_PASSWORD=do-not-return"
    (tmp_path / ".env.production").write_text(secret, encoding="utf-8")
    executor = ToolExecutor(tmp_path)

    result = executor.execute(
        Action(type=ActionType.READ_FILE, payload={"path": ".env.production"})
    )

    assert result.ok is False
    assert result.stderr == "denied_by_governance"
    assert secret not in result.stdout


def test_requires_approval_for_git_write_without_executing(tmp_path):
    executor = ToolExecutor(tmp_path)
    action = Action(type=ActionType.WRITE_FILE, payload={"path": ".git/config", "content": "x"})

    result = executor.execute(action)

    assert result.ok is False
    assert result.stderr == "approval_required"
    assert not (tmp_path / ".git" / "config").exists()


def test_requires_approval_for_high_risk_command_without_executing(tmp_path, monkeypatch):
    executor = ToolExecutor(tmp_path)
    action = Action(type=ActionType.RUN_COMMAND, payload={"command": "git push origin main"})

    def fail_if_run(*args, **kwargs):
        raise AssertionError("command execution should not be reached")

    monkeypatch.setattr("harness.tools.subprocess.run", fail_if_run)

    result = executor.execute(action)

    assert result.ok is False
    assert result.stderr == "approval_required"


def test_denies_non_string_command_without_executing(tmp_path, monkeypatch):
    executor = ToolExecutor(tmp_path)
    action = Action(type=ActionType.RUN_COMMAND, payload={"command": ["pytest"]})

    def fail_if_run(*args, **kwargs):
        raise AssertionError("command execution should not be reached")

    monkeypatch.setattr("harness.tools.subprocess.run", fail_if_run)

    result = executor.execute(action)

    assert result.ok is False
    assert result.stderr == "denied_by_governance"


def test_run_checks_short_circuits_after_pytest_failure(tmp_path, monkeypatch):
    executor = ToolExecutor(tmp_path)
    action = Action(type=ActionType.RUN_CHECKS, payload={})
    calls = []

    def run_command(action, command):
        calls.append(command)
        return ToolResult(action_id=action.request_id, ok=False, exit_code=1)

    monkeypatch.setattr(executor, "_run_command", run_command)

    result = executor.execute(action)

    assert result.ok is False
    assert calls == ["pytest"]

from harness.models import Action, ActionType
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
        payload={"command": "python -c \"import time; time.sleep(2)\""},
    )

    result = executor.execute(action)

    assert result.ok is False
    assert result.timed_out is True

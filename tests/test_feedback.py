from harness.feedback import parse_feedback
from harness.models import ToolResult


def test_parse_pytest_failure_summary():
    stderr = ""
    stdout = """
    FAILED tests/test_math.py::test_add - assert 3 == 4
    E       assert 3 == 4
    """
    result = ToolResult(
        action_id="act_pytest", ok=False, stdout=stdout, stderr=stderr, exit_code=1
    )

    feedback = parse_feedback(result)

    assert feedback.kind == "pytest_failure"
    assert "tests/test_math.py::test_add" in feedback.summary
    assert feedback.details["exit_code"] == 1


def test_parse_pytest_failure_when_stderr_contains_warning():
    stdout = "FAILED tests/test_math.py::test_add - assert 3 == 4"
    result = ToolResult(
        action_id="act_pytest",
        ok=False,
        stdout=stdout,
        stderr="warning: test environment is noisy",
        exit_code=1,
    )

    feedback = parse_feedback(result)

    assert feedback.kind == "pytest_failure"
    assert "tests/test_math.py::test_add" in feedback.summary


def test_parse_ruff_failure_summary():
    stdout = "src/app.py:3:1: F401 `os` imported but unused\nFound 1 error."
    result = ToolResult(action_id="act_ruff", ok=False, stdout=stdout, stderr="", exit_code=1)

    feedback = parse_feedback(result)

    assert feedback.kind == "ruff_failure"
    assert feedback.details["rule"] == "F401"
    assert feedback.details["file"] == "src/app.py"
    assert feedback.details["line"] == 3


def test_parse_ruff_failure_when_stderr_contains_warning():
    stdout = "src/app.py:3:1: F401 `os` imported but unused"
    result = ToolResult(
        action_id="act_ruff",
        ok=False,
        stdout=stdout,
        stderr="warning: cache unavailable",
        exit_code=1,
    )

    feedback = parse_feedback(result)

    assert feedback.kind == "ruff_failure"
    assert feedback.details["rule"] == "F401"


def test_parse_timeout_as_command_failure():
    result = ToolResult(
        action_id="act_cmd", ok=False, stdout="", stderr="", exit_code=None, timed_out=True
    )

    feedback = parse_feedback(result)

    assert feedback.kind == "command_timeout"
    assert "timed out" in feedback.summary

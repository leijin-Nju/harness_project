from harness.feedback import parse_feedback, redact_sensitive
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


def test_failure_feedback_includes_redacted_stdout_and_stderr():
    result = ToolResult(
        action_id="act_cmd",
        ok=False,
        stdout="partial result",
        stderr="API_TOKEN=plain-secret-value failed",
        exit_code=2,
    )

    feedback = parse_feedback(result)

    assert feedback.details["stdout"] == "partial result"
    assert "plain-secret-value" not in feedback.details["stderr"]
    assert "[redacted]" in feedback.details["stderr"]


def test_redacts_quoted_secret_assignments_and_authorization_headers():
    raw = (
        '{"api_key": "plain-secret-value"}\n'
        'API_TOKEN="plain-token-value"\n'
        "Authorization: Bearer bearer-secret-value\n"
    )

    redacted = redact_sensitive(raw)

    assert "plain-secret-value" not in redacted
    assert "plain-token-value" not in redacted
    assert "bearer-secret-value" not in redacted
    assert redacted.count("[redacted]") == 3

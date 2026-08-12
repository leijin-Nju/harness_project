import re

from harness.models import Feedback, ToolResult

RUFF_FAILURE_PATTERN = re.compile(r"^(.+?):(\d+):(\d+): ([A-Z]\d+) (.+)$", re.MULTILINE)
SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)(?<![A-Za-z0-9])(?:api[_-]?key|api[_-]?token|authorization|client[_-]?secret|"
    r"password|passwd|secret|token)"
    r"\s*[:=]\s*[^\s,;\"']+"
)
OPENAI_KEY_PATTERN = re.compile(r"sk-(?:[A-Za-z0-9]+-)+[A-Za-z0-9]+|sk-[A-Za-z0-9]{8,}")


def redact_sensitive(value: str) -> str:
    value = SECRET_ASSIGNMENT_PATTERN.sub("[redacted]", value)
    return OPENAI_KEY_PATTERN.sub("[redacted]", value)


def tool_observation(result: ToolResult) -> Feedback:
    if not result.ok:
        return parse_feedback(result)
    return Feedback(
        kind="tool_result",
        summary="Tool action completed successfully.",
        details={
            "ok": True,
            "exit_code": result.exit_code,
            "stdout": redact_sensitive(result.stdout),
            "stderr": redact_sensitive(result.stderr),
            "timed_out": result.timed_out,
        },
        source=result.action_id,
    )


def parse_feedback(result: ToolResult) -> Feedback:
    if result.timed_out:
        return Feedback(
            kind="command_timeout",
            summary="Command timed out.",
            details=_result_details(result),
            source=result.action_id,
            severity="error",
        )

    pytest_feedback = parse_pytest_failure(result)
    if pytest_feedback is not None:
        return pytest_feedback

    ruff_feedback = parse_ruff_failure(result)
    if ruff_feedback is not None:
        return ruff_feedback

    return parse_command_failure(result)


def parse_pytest_failure(result: ToolResult) -> Feedback | None:
    for line in _output(result).splitlines():
        failure_line = line.strip()
        if failure_line.startswith("FAILED "):
            node_id = failure_line.removeprefix("FAILED ").split(" - ", maxsplit=1)[0]
            return Feedback(
                kind="pytest_failure",
                summary=f"Pytest failure: {node_id}",
                details={**_result_details(result), "node_id": node_id},
                source=result.action_id,
                severity="error",
            )
    return None


def parse_ruff_failure(result: ToolResult) -> Feedback | None:
    match = RUFF_FAILURE_PATTERN.search(_output(result))
    if match is None:
        return None

    file_path, line, column, rule, message = match.groups()
    return Feedback(
        kind="ruff_failure",
        summary=f"Ruff failure: {file_path}:{line}: {message}",
        details={
            **_result_details(result),
            "file": file_path,
            "line": int(line),
            "column": int(column),
            "rule": rule,
        },
        source=result.action_id,
        severity="error",
    )


def parse_command_failure(result: ToolResult) -> Feedback:
    return Feedback(
        kind="command_failure",
        summary=f"Command failed with exit code {result.exit_code}.",
        details=_result_details(result),
        source=result.action_id,
        severity="error",
    )


def _output(result: ToolResult) -> str:
    return "\n".join(output for output in (result.stderr, result.stdout) if output)


def _result_details(result: ToolResult) -> dict[str, object]:
    return {
        "exit_code": result.exit_code,
        "stdout": redact_sensitive(result.stdout),
        "stderr": redact_sensitive(result.stderr),
        "timed_out": result.timed_out,
    }

import re

from harness.models import Feedback, ToolResult

RUFF_FAILURE_PATTERN = re.compile(r"^(.+?):(\d+):(\d+): ([A-Z]\d+) (.+)$", re.MULTILINE)


def parse_feedback(result: ToolResult) -> Feedback:
    if result.timed_out:
        return Feedback(
            kind="command_timeout",
            summary="Command timed out.",
            details={"exit_code": result.exit_code},
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
                details={"exit_code": result.exit_code, "node_id": node_id},
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
            "exit_code": result.exit_code,
            "file": file_path,
            "line": int(line),
            "column": int(column),
            "rule": rule,
        },
        source=result.action_id,
        severity="error",
    )


def parse_command_failure(result: ToolResult) -> Feedback:
    output = _output(result)[:1000]
    return Feedback(
        kind="command_failure",
        summary=f"Command failed with exit code {result.exit_code}.",
        details={"exit_code": result.exit_code, "output": output},
        source=result.action_id,
        severity="error",
    )


def _output(result: ToolResult) -> str:
    return result.stderr or result.stdout

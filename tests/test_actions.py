import pytest

from harness.actions import build_action_schema, parse_action
from harness.models import ActionType


def test_parse_action_from_json_string():
    action = parse_action('{"type": "run_command", "payload": {"command": "pytest"}}')

    assert action.type == ActionType.RUN_COMMAND
    assert action.payload == {"command": "pytest"}


def test_parse_action_rejects_unknown_action_type():
    with pytest.raises(ValueError, match="unknown action type"):
        parse_action('{"type": "delete_internet", "payload": {}}')


def test_action_schema_lists_supported_actions():
    schema = build_action_schema()

    assert "run_command" in schema["properties"]["type"]["enum"]
    assert "request_done" in schema["properties"]["type"]["enum"]

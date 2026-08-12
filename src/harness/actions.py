import json
from pathlib import Path

from harness.models import Action, ActionType


def parse_action(raw: str | dict) -> Action:
    """Parse an action from JSON text or a mapping."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("invalid action JSON") from exc

    if not isinstance(raw, dict):
        raise ValueError("action must be a JSON object")
    if "type" not in raw:
        raise ValueError("action missing required field: type")
    if "payload" not in raw:
        raise ValueError("action missing required field: payload")

    try:
        action_type = ActionType(raw["type"])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"unknown action type: {raw['type']}") from exc

    try:
        action = Action(type=action_type, payload=raw["payload"])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid action: {exc}") from exc
    validate_action_payload(action)
    return action


def validate_action_payload(action: Action) -> None:
    """Validate the fields consumed by governance and tool dispatch."""
    payload = action.payload
    if action.type in {ActionType.READ_FILE, ActionType.WRITE_FILE}:
        if not isinstance(payload.get("path"), (str, Path)):
            raise ValueError(f"{action.type.value} requires a path")
    if action.type == ActionType.WRITE_FILE and not isinstance(payload.get("content"), str):
        raise ValueError("write_file requires string content")
    if action.type == ActionType.RUN_COMMAND and not isinstance(payload.get("command"), str):
        raise ValueError("run_command requires a string command")


def build_action_schema() -> dict[str, object]:
    return {
        "type": "object",
        "properties": {
            "type": {"type": "string", "enum": [action.value for action in ActionType]},
            "payload": {"type": "object"},
        },
        "required": ["type", "payload"],
        "additionalProperties": False,
    }

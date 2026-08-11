import json

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
        return Action(type=action_type, payload=raw["payload"])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid action: {exc}") from exc


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

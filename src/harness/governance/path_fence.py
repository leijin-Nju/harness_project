from pathlib import Path

from harness.models import Action, ActionType, RiskDecision, RiskLevel


class PathFenceError(ValueError):
    """Raised when an action does not contain a usable path."""


class PathFence:
    _SENSITIVE_NAMES = {".env", ".env.local", ".npmrc", ".pypirc", "id_rsa", "id_ed25519"}

    def __init__(self, workspace_root: Path | str):
        self.workspace_root = Path(workspace_root).resolve(strict=False)

    def resolve(self, candidate: Path | str) -> Path:
        return Path(candidate).resolve(strict=False) if Path(candidate).is_absolute() else (
            self.workspace_root / candidate
        ).resolve(strict=False)

    def check_action(self, action: Action) -> RiskDecision:
        if action.type not in {ActionType.READ_FILE, ActionType.WRITE_FILE}:
            return RiskDecision(
                level=RiskLevel.DENY,
                reasons=["unsupported action type for path fence"],
            )

        candidate = action.payload.get("path")
        if not isinstance(candidate, (Path, str)):
            raise PathFenceError("action payload must contain a path")

        resolved = self.resolve(candidate)
        try:
            resolved.relative_to(self.workspace_root)
        except ValueError:
            return RiskDecision(level=RiskLevel.DENY, reasons=["path is outside workspace"])

        if resolved.name.casefold() in self._SENSITIVE_NAMES:
            return RiskDecision(
                level=RiskLevel.DENY,
                reasons=["path is a sensitive credential file"],
            )

        try:
            relative = resolved.relative_to(self.workspace_root)
        except ValueError:
            return RiskDecision(level=RiskLevel.DENY, reasons=["path is outside workspace"])
        if ".git" in relative.parts:
            return RiskDecision(level=RiskLevel.REVIEW, reasons=["path is git metadata"])

        return RiskDecision(level=RiskLevel.ALLOW, reasons=["path is inside workspace"])

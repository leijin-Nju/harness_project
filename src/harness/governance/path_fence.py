import re
from pathlib import Path

from harness.models import Action, ActionType, RiskDecision, RiskLevel


class PathFenceError(ValueError):
    """Raised when an action does not contain a usable path."""


class PathFence:
    _SENSITIVE_NAMES = {
        ".git-credentials",
        ".netrc",
        ".npmrc",
        ".pypirc",
        "credentials",
        "credentials.json",
        "id_ed25519",
        "id_rsa",
        "known_hosts",
    }
    _SENSITIVE_DIRS = {".aws", ".azure", ".docker", ".kube", ".ssh"}
    _SECRET_NAME_PATTERN = re.compile(
        r"(?:^|[._-])(api[_-]?key|client[_-]?secret|password|passwd|private[_-]?key|"
        r"secret|service[_-]?account|token)(?:[._-]|$)",
        re.IGNORECASE,
    )

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

        relative = resolved.relative_to(self.workspace_root)
        parts = tuple(part.casefold() for part in relative.parts)
        name = resolved.name.casefold()
        is_cloud_config = any(
            parts[index : index + 2] == (".config", "gcloud")
            for index in range(len(parts) - 1)
        )
        if (
            name == ".env"
            or name.startswith(".env.")
            or name in self._SENSITIVE_NAMES
            or any(part in self._SENSITIVE_DIRS for part in parts[:-1])
            or is_cloud_config
            or self._SECRET_NAME_PATTERN.search(name)
        ):
            return RiskDecision(
                level=RiskLevel.DENY,
                reasons=["path is a sensitive credential file"],
            )

        if ".git" in parts:
            return RiskDecision(level=RiskLevel.REVIEW, reasons=["path is git metadata"])

        return RiskDecision(level=RiskLevel.ALLOW, reasons=["path is inside workspace"])

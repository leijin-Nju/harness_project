import shlex

from harness.models import Action, ActionType, RiskDecision, RiskLevel


class RiskClassifier:
    _DENY_PATTERNS = (
        "drop database",
        "truncate table",
        ".env",
        ".npmrc",
        ".pypirc",
        "id_rsa",
        "id_ed25519",
        "rm -rf /",
        "del /s",
        "format",
    )
    _REVIEW_PREFIXES = (
        ("git", "push"),
        ("pip", "install"),
        ("npm", "install"),
        ("poetry", "add"),
        ("curl",),
        ("wget",),
        ("uvicorn",),
        ("python", "-m", "http.server"),
    )
    _ALLOW_PREFIXES = (
        ("pytest",),
        ("python", "-m", "pytest"),
        ("ruff",),
        ("git", "status"),
        ("git", "diff"),
    )

    def classify(self, action: Action) -> RiskDecision:
        if action.type != ActionType.RUN_COMMAND:
            return RiskDecision(level=RiskLevel.ALLOW, reasons=["non-command action"])

        command = action.payload.get("command", "")
        if not isinstance(command, str):
            return RiskDecision(level=RiskLevel.ALLOW, reasons=["command is not a string"])

        parts = [part.lower() for part in shlex.split(command, posix=False)]
        normalized = " ".join(parts)

        if any(pattern in normalized for pattern in self._DENY_PATTERNS):
            return RiskDecision(level=RiskLevel.DENY, reasons=["command matches a deny pattern"])

        if "--host 0.0.0.0" in normalized or self._starts_with(parts, self._REVIEW_PREFIXES):
            return RiskDecision(level=RiskLevel.REVIEW, reasons=["command requires review"])

        if self._starts_with(parts, self._ALLOW_PREFIXES):
            return RiskDecision(level=RiskLevel.ALLOW, reasons=["command is explicitly allowed"])

        return RiskDecision(level=RiskLevel.ALLOW, reasons=["command has no elevated risk pattern"])

    @staticmethod
    def _starts_with(parts: list[str], prefixes: tuple[tuple[str, ...], ...]) -> bool:
        return any(tuple(parts[: len(prefix)]) == prefix for prefix in prefixes)

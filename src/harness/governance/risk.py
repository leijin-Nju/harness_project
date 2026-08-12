import re
import shlex

from harness.models import Action, ActionType, RiskDecision, RiskLevel


class RiskClassifier:
    _SHELL_OPERATOR_PATTERN = re.compile(r"[;&|<>`\r\n]|\$\(")
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
    _WRAPPER_PREFIXES = (
        ("cmd",),
        ("cmd.exe",),
        ("powershell",),
        ("powershell.exe",),
        ("pwsh",),
        ("bash",),
        ("sh",),
    )
    _ALLOW_PREFIXES = (
        ("pytest",),
        ("python", "-m", "pytest"),
        ("ruff", "check"),
        ("git", "status"),
        ("git", "diff"),
    )

    def classify(self, action: Action) -> RiskDecision:
        if action.type != ActionType.RUN_COMMAND:
            return RiskDecision(level=RiskLevel.ALLOW, reasons=["non-command action"])

        command = action.payload.get("command")
        if not isinstance(command, str):
            return RiskDecision(level=RiskLevel.DENY, reasons=["command is not a string"])

        if not command.strip():
            return RiskDecision(level=RiskLevel.DENY, reasons=["command is empty"])

        try:
            parts = [part.lower() for part in shlex.split(command, posix=False)]
        except ValueError:
            return RiskDecision(level=RiskLevel.DENY, reasons=["command cannot be parsed safely"])
        normalized = " ".join(parts)

        if any(pattern in normalized for pattern in self._DENY_PATTERNS):
            return RiskDecision(level=RiskLevel.DENY, reasons=["command matches a deny pattern"])

        if self._SHELL_OPERATOR_PATTERN.search(command):
            return RiskDecision(
                level=RiskLevel.REVIEW,
                reasons=["composite shell command requires review"],
            )

        if self._starts_with(parts, self._WRAPPER_PREFIXES):
            return RiskDecision(level=RiskLevel.REVIEW, reasons=["shell wrapper requires review"])

        if "--host 0.0.0.0" in normalized or self._starts_with(parts, self._REVIEW_PREFIXES):
            return RiskDecision(level=RiskLevel.REVIEW, reasons=["command requires review"])

        if self._is_mock_demo(parts):
            return RiskDecision(level=RiskLevel.ALLOW, reasons=["command is explicitly allowed"])

        if self._is_safe_python_inline(parts):
            return RiskDecision(level=RiskLevel.ALLOW, reasons=["command is explicitly allowed"])

        if self._starts_with(parts, self._ALLOW_PREFIXES):
            return RiskDecision(level=RiskLevel.ALLOW, reasons=["command is explicitly allowed"])

        return RiskDecision(level=RiskLevel.REVIEW, reasons=["unknown command requires review"])

    @staticmethod
    def _is_mock_demo(parts: list[str]) -> bool:
        if len(parts) < 2 or parts[0] != "python":
            return False
        script = parts[1].replace("\\", "/").casefold()
        return script == "scripts/mock_demo.py"

    @staticmethod
    def _is_safe_python_inline(parts: list[str]) -> bool:
        if len(parts) != 3 or parts[:2] != ["python", "-c"]:
            return False
        code = parts[2].strip('"').strip("'")
        return bool(
            re.fullmatch(r"print\((?:'[^']*'|\"[^\"]*\")\)", code)
            or re.fullmatch(r"__import__\((?:'time'|\"time\")\)\.sleep\(\d+(?:\.\d+)?\)", code)
        )

    @staticmethod
    def _starts_with(parts: list[str], prefixes: tuple[tuple[str, ...], ...]) -> bool:
        return any(tuple(parts[: len(prefix)]) == prefix for prefix in prefixes)

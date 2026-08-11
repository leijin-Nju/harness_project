from pathlib import Path

from pydantic import BaseModel


class HarnessConfig(BaseModel):
    workspace_root: Path
    llm_provider: str = "openai-compatible"
    default_timeout_seconds: float = 10.0
    max_iterations: int = 8

    def paths(self) -> dict[str, Path]:
        state_dir = self.workspace_root / ".harness"
        return {
            "state_dir": state_dir,
            "runs_dir": state_dir / "runs",
            "approvals": state_dir / "approvals.json",
            "memory": state_dir / "memory.json",
            "logs_dir": state_dir / "logs",
        }

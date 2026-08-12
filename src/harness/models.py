from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


def _now() -> datetime:
    return datetime.now(UTC)


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class ActionType(str, Enum):  # noqa: UP042
    READ_FILE = "read_file"
    WRITE_FILE = "write_file"
    RUN_COMMAND = "run_command"
    RUN_CHECKS = "run_checks"
    REMEMBER = "remember"
    REQUEST_DONE = "request_done"


class RiskLevel(str, Enum):  # noqa: UP042
    ALLOW = "allow"
    REVIEW = "review"
    DENY = "deny"


class RunStatus(str, Enum):  # noqa: UP042
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    MAX_ITERATIONS = "max_iterations"


class ApprovalStatus(str, Enum):  # noqa: UP042
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class MemoryKind(str, Enum):  # noqa: UP042
    CONVENTION = "convention"
    DECISION = "decision"
    FAILURE_SUMMARY = "failure_summary"


class Action(BaseModel):
    type: ActionType
    payload: dict[str, Any]
    request_id: str = Field(default_factory=lambda: _id("act"))
    created_at: datetime = Field(default_factory=_now)


class RiskDecision(BaseModel):
    level: RiskLevel
    reasons: list[str]
    required_approval: bool = False
    policy_version: str = "2026-08-10"

    @model_validator(mode="after")
    def require_approval_for_review(self) -> "RiskDecision":
        if self.level == RiskLevel.REVIEW:
            self.required_approval = True
        return self


class ToolResult(BaseModel):
    action_id: str
    ok: bool
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    timed_out: bool = False
    duration_ms: int | None = None

    @field_validator("stdout", "stderr")
    @classmethod
    def truncate_output(cls, value: str) -> str:
        limit = 4096
        suffix = "[truncated]"
        if len(value) <= limit:
            return value
        return value[: limit - len(suffix)] + suffix


class Feedback(BaseModel):
    kind: str
    summary: str
    details: dict[str, Any] | str = ""
    source: str = ""
    severity: str = "info"


class ApprovalRequest(BaseModel):
    id: str = Field(default_factory=lambda: _id("apr"))
    action: Action
    risk_decision: RiskDecision
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: datetime = Field(default_factory=_now)
    resolved_at: datetime | None = None
    resolution_note: str | None = None


class MemoryEntry(BaseModel):
    id: str = Field(default_factory=lambda: _id("mem"))
    kind: MemoryKind
    text: str
    keywords: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_now)
    last_used_at: datetime | None = None
    source_task_id: str | None = None


class TaskRun(BaseModel):
    id: str = Field(default_factory=lambda: _id("run"))
    workspace: str
    task: str
    status: RunStatus = RunStatus.RUNNING
    iterations: int = 0
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
    stop_reason: str | None = None
    pending_approval_id: str | None = None
    observations: list[Feedback] = Field(default_factory=list)


class CredentialStatus(BaseModel):
    provider: str
    source: str
    exists: bool
    updated_at: datetime = Field(default_factory=_now)
    masked_preview: str | None = None

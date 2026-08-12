from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from harness.models import (
    Action,
    ApprovalRequest,
    ApprovalStatus,
    RiskDecision,
)


class JsonApprovalStore:
    def __init__(self, path: Path | str):
        self.path = Path(path)

    def create(self, action: Action, risk_decision: RiskDecision) -> ApprovalRequest:
        request = ApprovalRequest(action=action, risk_decision=risk_decision)
        requests = self._load()
        requests.append(request)
        self._save(requests)
        return request

    def get(self, request_id: str) -> ApprovalRequest:
        for request in self._load():
            if request.id == request_id:
                return request
        raise KeyError(request_id)

    def list(self, status: ApprovalStatus | None = None) -> list[ApprovalRequest]:
        requests = self._load()
        if status is None:
            return requests
        return [request for request in requests if request.status == status]

    def resolve(
        self,
        request_id: str,
        status: ApprovalStatus,
        note: str = "",
    ) -> ApprovalRequest:
        if status in {ApprovalStatus.PENDING, ApprovalStatus.CONSUMED}:
            raise ValueError(f"approval status cannot be {status.value}")
        requests = self._load()
        for index, request in enumerate(requests):
            if request.id != request_id:
                continue
            if request.status != ApprovalStatus.PENDING:
                raise ValueError("approval request is not pending")
            resolved = request.model_copy(
                update={
                    "status": status,
                    "resolved_at": datetime.now(UTC),
                    "resolution_note": note,
                }
            )
            requests[index] = resolved
            self._save(requests)
            return resolved
        raise KeyError(request_id)

    def consume(self, request_id: str, note: str = "consumed") -> ApprovalRequest:
        requests = self._load()
        for index, request in enumerate(requests):
            if request.id != request_id:
                continue
            if request.status == ApprovalStatus.CONSUMED:
                return request
            if request.status != ApprovalStatus.APPROVED:
                raise ValueError("approval request is not approved")
            consumed = request.model_copy(
                update={
                    "status": ApprovalStatus.CONSUMED,
                    "resolved_at": datetime.now(UTC),
                    "resolution_note": note,
                }
            )
            requests[index] = consumed
            self._save(requests)
            return consumed
        raise KeyError(request_id)

    def _load(self) -> list[ApprovalRequest]:
        if not self.path.exists():
            return []
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return [ApprovalRequest.model_validate(item) for item in data]

    def _save(self, requests: list[ApprovalRequest]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps([request.model_dump(mode="json") for request in requests]),
            encoding="utf-8",
        )
        temporary.replace(self.path)


class ApprovalStateMachine:
    def __init__(self, store: JsonApprovalStore):
        self.store = store

    def approve(self, request_id: str, note: str = "") -> ApprovalRequest:
        return self.store.resolve(request_id, ApprovalStatus.APPROVED, note)

    def reject(self, request_id: str, note: str = "") -> ApprovalRequest:
        return self.store.resolve(request_id, ApprovalStatus.REJECTED, note)

    def expire(self, request_id: str, note: str = "expired") -> ApprovalRequest:
        return self.store.resolve(request_id, ApprovalStatus.EXPIRED, note)

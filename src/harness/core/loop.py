import json
from datetime import UTC, datetime

from harness.actions import build_action_schema, parse_action
from harness.config import HarnessConfig
from harness.feedback import redact_sensitive, tool_observation
from harness.governance.approval import JsonApprovalStore
from harness.governance.path_fence import PathFence
from harness.governance.risk import RiskClassifier
from harness.llm import LLMClient
from harness.memory import JsonMemoryStore, MemoryStore
from harness.models import (
    Action,
    ActionType,
    ApprovalStatus,
    Feedback,
    MemoryEntry,
    MemoryKind,
    RiskDecision,
    RiskLevel,
    RunStatus,
    TaskRun,
)
from harness.tools import ToolExecutor


class AgentLoop:
    def __init__(
        self,
        config: HarnessConfig,
        llm: LLMClient,
        approval_store: JsonApprovalStore | None = None,
        memory_store: MemoryStore | None = None,
        tool_executor: ToolExecutor | None = None,
    ) -> None:
        self.config = config
        self.llm = llm
        paths = config.paths()
        self.approval_store = approval_store or JsonApprovalStore(paths["approvals"])
        self.memory_store = memory_store or JsonMemoryStore(paths["memory"])
        self.tool_executor = tool_executor or ToolExecutor(
            config.workspace_root, config.default_timeout_seconds
        )
        self.path_fence = PathFence(config.workspace_root)
        self.risk_classifier = RiskClassifier()

    def run(self, task: str) -> TaskRun:
        run = TaskRun(workspace=str(self.config.workspace_root), task=task)
        return self._run(run)

    def resume(self, run_id: str) -> TaskRun:
        run_path = self.config.paths()["runs_dir"] / f"{run_id}.json"
        run = TaskRun.model_validate_json(run_path.read_text(encoding="utf-8"))
        if run.pending_approval_id is not None:
            return self._resume_approval(run)
        if run.status in {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.MAX_ITERATIONS}:
            return run
        run.status = RunStatus.RUNNING
        run.stop_reason = None
        return self._run(run)

    def _resume_approval(self, run: TaskRun) -> TaskRun:
        request = self.approval_store.get(run.pending_approval_id)
        if request.status == ApprovalStatus.PENDING:
            return self._finish(run, RunStatus.WAITING_FOR_APPROVAL, "approval_required")
        if request.status == ApprovalStatus.CONSUMED:
            run.pending_approval_id = None
            return self._finish(run, RunStatus.COMPLETED, "approval_consumed")
        run.pending_approval_id = None
        if request.status in {ApprovalStatus.REJECTED, ApprovalStatus.EXPIRED}:
            reason = f"approval_{request.status.value}"
            return self._finish(run, RunStatus.FAILED, reason)

        request = self.approval_store.consume(request.id)
        run.status = RunStatus.RUNNING
        run.stop_reason = None
        self._persist(run)
        try:
            result = self.tool_executor.execute_approved(request.action)
        except (KeyError, OSError, TypeError, ValueError) as error:
            run.observations.append(self._invalid_action_feedback(error))
        else:
            run.observations.append(tool_observation(result))
        self._persist(run)
        return self._run(run)

    def _run(self, run: TaskRun) -> TaskRun:
        while run.iterations < self.config.max_iterations:
            messages = self._messages(run.task, run.observations)
            raw_action = self.llm.generate(messages, build_action_schema())
            run.iterations += 1
            try:
                action = parse_action(raw_action)
                decision = self._governance_decision(action)
                if decision.level == RiskLevel.DENY:
                    run.observations.append(self._governance_feedback(action, decision))
                    return self._finish(run, RunStatus.FAILED, "denied_by_governance")
                if decision.level == RiskLevel.REVIEW:
                    request = self.approval_store.create(action, decision)
                    run.pending_approval_id = request.id
                    return self._finish(
                        run,
                        RunStatus.WAITING_FOR_APPROVAL,
                        "approval_required",
                    )
                if action.type == ActionType.REMEMBER:
                    self.memory_store.add(self._memory_entry(action, run.id))
                    self._persist(run)
                    continue
                if action.type == ActionType.REQUEST_DONE:
                    return self._finish(run, RunStatus.COMPLETED, "request_done")

                result = self.tool_executor.execute(action)
                run.observations.append(tool_observation(result))
            except (KeyError, OSError, TypeError, ValueError) as error:
                run.observations.append(self._invalid_action_feedback(error))
            finally:
                self._persist(run)

        return self._finish(run, RunStatus.MAX_ITERATIONS, "max_iterations")

    def _messages(self, task: str, feedback: list[Feedback]) -> list[dict[str, str]]:
        memories = self.memory_store.search(task)
        context = {
            "task": task,
            "recent_observations": [item.model_dump(mode="json") for item in feedback[-5:]],
            "memory": [item.text for item in memories],
        }
        return [{"role": "user", "content": json.dumps(context, ensure_ascii=True)}]

    def _governance_decision(self, action: Action) -> RiskDecision:
        if action.type in {ActionType.READ_FILE, ActionType.WRITE_FILE}:
            return self.path_fence.check_action(action)
        if action.type == ActionType.RUN_COMMAND:
            return self.risk_classifier.classify(action)
        return RiskDecision(
            level=RiskLevel.ALLOW,
            reasons=["action does not require pre-execution review"],
        )

    @staticmethod
    def _governance_feedback(action: Action, decision: RiskDecision) -> Feedback:
        return Feedback(
            kind="governance_denial",
            summary="Action denied by governance.",
            details={"action": action.type.value, "reasons": decision.reasons},
            source=action.request_id,
            severity="error",
        )

    @staticmethod
    def _invalid_action_feedback(error: Exception) -> Feedback:
        return Feedback(
            kind="invalid_action",
            summary="The proposed action was invalid and was not executed.",
            details={"error": redact_sensitive(str(error))[:1000]},
            severity="error",
        )

    @staticmethod
    def _memory_entry(action: Action, run_id: str) -> MemoryEntry:
        payload = action.payload
        kind = MemoryKind(payload.get("kind", MemoryKind.DECISION))
        return MemoryEntry(
            kind=kind,
            text=str(payload.get("text", "")),
            keywords=[str(item) for item in payload.get("keywords", [])],
            source_task_id=run_id,
        )

    def _finish(self, run: TaskRun, status: RunStatus, reason: str) -> TaskRun:
        run.status = status
        run.stop_reason = reason
        self._persist(run)
        return run

    def _persist(self, run: TaskRun) -> None:
        run.updated_at = datetime.now(UTC)
        path = self.config.paths()["runs_dir"] / f"{run.id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(run.model_dump_json(), encoding="utf-8")

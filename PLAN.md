# Coding Agent Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python Coding Agent Harness MVP with a self-owned agent loop, deterministic governance, structured feedback, JSON memory, safe credentials, CLI, minimal WebUI, Docker distribution, and mock-LLM tests.

**Architecture:** The project is a Python package under `src/harness`. Core behavior flows through Pydantic models, a mockable LLM interface, action parsing, governance checks, tool execution, feedback parsing, JSON persistence, and a loop coordinator. CLI and WebUI are thin adapters over the same core services; tests use deterministic mock LLM scripts and never require network or a real API key.

**Tech Stack:** Python 3.11+, Pydantic v2, Typer, FastAPI, pytest, ruff, keyring, OpenAI-compatible HTTP client abstraction, Docker/OCI, GitLab CI.

## Global Constraints

- Use Python 3.11+.
- Use Pydantic for action, feedback, approval, credential, memory, and run-state boundary models.
- Default memory storage is local JSON; do not use SQLite.
- A MySQL memory adapter may be reserved as an interface, but MVP does not require MySQL deployment.
- Do not use LangChain `AgentExecutor`, AutoGen, CrewAI, LlamaIndex agents, or any existing agent runner.
- `OpenAICompatibleClient` may only perform a single model call; it must not own the agent loop.
- Core tests must run with mock LLM, no network, and no real API key.
- All shell command execution must set a finite timeout.
- High-risk actions must be denied or routed to HITL before execution.
- Credentials must never be hardcoded, committed, logged, or displayed in plaintext.
- CLI is primary; WebUI is a minimal display and approval adapter.
- Docker is the primary distribution path.
- `.gitlab-ci.yml` must contain a job named `unit-test`.

---

## Scope Check

The confirmed spec describes one integrated MVP rather than independent sub-projects. The subsystems are separable by module, but they depend on shared domain models and one agent loop. This plan therefore builds the project task-by-task in one implementation stream, with governance and feedback tests established before CLI/WebUI distribution work.

## File Structure

- `pyproject.toml`: package metadata, dependencies, pytest and ruff configuration.
- `Makefile`: stable local commands, including `make test`, `make lint`, `make demo`.
- `.gitignore`: excludes virtualenvs, caches, `.env`, `.harness/`, build outputs.
- `src/harness/__init__.py`: package version.
- `src/harness/models.py`: Pydantic boundary models and enums shared across modules.
- `src/harness/actions.py`: action parsing, validation, and helper constructors.
- `src/harness/llm.py`: `LLMClient`, `MockLLMClient`, `OpenAICompatibleClient`.
- `src/harness/governance/path_fence.py`: workspace path validation.
- `src/harness/governance/risk.py`: deterministic command/action risk classifier.
- `src/harness/governance/approval.py`: approval store and state machine.
- `src/harness/memory.py`: `MemoryStore`, `JsonMemoryStore`, MySQL interface placeholder class that raises a clear unsupported error.
- `src/harness/tools.py`: file and command tool execution with timeouts.
- `src/harness/feedback.py`: pytest, ruff, and generic command feedback parsers.
- `src/harness/config.py`: app config loading and default paths.
- `src/harness/credentials.py`: keyring/env credential sources and masking.
- `src/harness/core/loop.py`: self-owned agent loop.
- `src/harness/cli.py`: Typer CLI commands.
- `src/harness/web.py`: FastAPI app and minimal HTML responses.
- `tests/`: unit and integration tests mirroring the modules above.
- `examples/mock_project/`: tiny project used by mock loop/demo tests.
- `scripts/mock_demo.py`: deterministic mechanism demo entrypoint.
- `Dockerfile`: container image.
- `.gitlab-ci.yml`: unit-test and Docker build jobs.
- `SPEC.md`, `PLAN.md`, `SPEC_PROCESS.md`, `AGENT_LOG.md`, `REFLECTION.md`, `README.md`: course deliverables and process documentation.

## Task Dependencies

Task 1 creates the package base and shared models. Tasks 2-8 build independent mechanisms on top of those models. Task 9 integrates them into the loop. Tasks 10-12 expose CLI/WebUI and deterministic demo behavior. Tasks 13-14 package, document, and prepare CI. Task 15 performs final verification and process updates.

---

### Task 1: Project Skeleton And Shared Models

**Files:**
- Create: `pyproject.toml`
- Create: `Makefile`
- Create: `.gitignore`
- Create: `src/harness/__init__.py`
- Create: `src/harness/models.py`
- Create: `tests/test_models.py`

**Interfaces:**
- Consumes: no project code.
- Produces:
  - `ActionType(str, Enum)`: `READ_FILE`, `WRITE_FILE`, `RUN_COMMAND`, `RUN_CHECKS`, `REMEMBER`, `REQUEST_DONE`
  - `RiskLevel(str, Enum)`: `ALLOW`, `REVIEW`, `DENY`
  - `RunStatus(str, Enum)`: `RUNNING`, `COMPLETED`, `FAILED`, `WAITING_FOR_APPROVAL`, `MAX_ITERATIONS`
  - `ApprovalStatus(str, Enum)`: `PENDING`, `APPROVED`, `REJECTED`, `EXPIRED`
  - `MemoryKind(str, Enum)`: `CONVENTION`, `DECISION`, `FAILURE_SUMMARY`
  - Pydantic models: `Action`, `RiskDecision`, `ToolResult`, `Feedback`, `ApprovalRequest`, `MemoryEntry`, `TaskRun`, `CredentialStatus`

- [x] **Step 1: Write the failing model tests**

Create `tests/test_models.py`:

```python
from harness.models import (
    Action,
    ActionType,
    ApprovalRequest,
    ApprovalStatus,
    RiskDecision,
    RiskLevel,
    ToolResult,
)


def test_action_model_requires_known_type():
    action = Action(type=ActionType.RUN_COMMAND, payload={"command": "pytest"})

    assert action.type == ActionType.RUN_COMMAND
    assert action.payload["command"] == "pytest"
    assert action.request_id.startswith("act_")


def test_risk_decision_defaults_to_not_requiring_approval_for_allow():
    decision = RiskDecision(level=RiskLevel.ALLOW, reasons=["safe validation command"])

    assert decision.required_approval is False
    assert decision.policy_version == "2026-08-10"


def test_approval_request_starts_pending():
    action = Action(type=ActionType.RUN_COMMAND, payload={"command": "git push"})
    decision = RiskDecision(level=RiskLevel.REVIEW, reasons=["publishes external state"])
    request = ApprovalRequest(action=action, risk_decision=decision)

    assert request.status == ApprovalStatus.PENDING
    assert request.id.startswith("apr_")


def test_tool_result_truncates_long_stdout():
    result = ToolResult(action_id="act_test", ok=False, stdout="x" * 6000, stderr="", exit_code=1)

    assert len(result.stdout) <= 4096
    assert result.stdout.endswith("[truncated]")
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py -v`

Expected: FAIL during import with `ModuleNotFoundError: No module named 'harness'` or missing model names.

- [x] **Step 3: Add project metadata and minimal models**

Create `pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=69", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "coding-agent-harness"
version = "0.1.0"
description = "A self-owned coding agent harness with deterministic governance and feedback."
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.111",
  "httpx>=0.27",
  "keyring>=25",
  "pydantic>=2.7",
  "typer>=0.12",
  "uvicorn>=0.30",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.2",
  "ruff>=0.5",
]

[project.scripts]
harness = "harness.cli:app"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]
```

Create `Makefile`:

```makefile
.PHONY: test lint demo

test:
	pytest -q

lint:
	ruff check src tests

demo:
	python scripts/mock_demo.py
```

Create `.gitignore`:

```gitignore
.venv/
__pycache__/
.pytest_cache/
.ruff_cache/
.env
.harness/
build/
dist/
*.egg-info/
```

Create `src/harness/__init__.py`:

```python
__version__ = "0.1.0"
```

Create `src/harness/models.py` with the exact public names listed in **Interfaces**. Use `Field(default_factory=...)` to generate `act_`, `apr_`, `mem_`, and `run_` ids with `uuid.uuid4().hex[:12]`. Use a field validator or model validator on `ToolResult` to truncate `stdout` and `stderr` to 4096 characters and append `[truncated]`.

- [x] **Step 4: Run tests and lint**

Run: `pytest tests/test_models.py -v`

Expected: PASS.

Run: `ruff check src tests`

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add pyproject.toml Makefile .gitignore src/harness/__init__.py src/harness/models.py tests/test_models.py
git commit -m "feat: add harness project skeleton and shared models"
```

---

### Task 2: Action Parsing And LLM Abstraction

**Files:**
- Create: `src/harness/actions.py`
- Create: `src/harness/llm.py`
- Create: `tests/test_actions.py`
- Create: `tests/test_llm.py`

**Interfaces:**
- Consumes: `Action`, `ActionType` from `harness.models`.
- Produces:
  - `parse_action(raw: str | dict) -> Action`
  - `build_action_schema() -> dict[str, object]`
  - `LLMClient.generate(messages: list[dict[str, str]], action_schema: dict[str, object]) -> str`
  - `MockLLMClient(script: list[str | dict])`
  - `OpenAICompatibleClient(api_key: str, base_url: str, model: str, timeout_seconds: float = 30.0)`

- [x] **Step 1: Write failing tests for parsing and mock LLM**

Create `tests/test_actions.py`:

```python
import pytest

from harness.actions import build_action_schema, parse_action
from harness.models import ActionType


def test_parse_action_from_json_string():
    action = parse_action('{"type": "run_command", "payload": {"command": "pytest"}}')

    assert action.type == ActionType.RUN_COMMAND
    assert action.payload == {"command": "pytest"}


def test_parse_action_rejects_unknown_action_type():
    with pytest.raises(ValueError, match="unknown action type"):
        parse_action('{"type": "delete_internet", "payload": {}}')


def test_action_schema_lists_supported_actions():
    schema = build_action_schema()

    assert "run_command" in schema["properties"]["type"]["enum"]
    assert "request_done" in schema["properties"]["type"]["enum"]
```

Create `tests/test_llm.py`:

```python
import pytest

from harness.llm import MockLLMClient, OpenAICompatibleClient


def test_mock_llm_returns_scripted_steps():
    client = MockLLMClient([
        {"type": "read_file", "payload": {"path": "README.md"}},
        '{"type": "request_done", "payload": {"summary": "done"}}',
    ])

    assert "read_file" in client.generate([], {})
    assert "request_done" in client.generate([], {})


def test_mock_llm_raises_when_script_exhausted():
    client = MockLLMClient([])

    with pytest.raises(RuntimeError, match="script exhausted"):
        client.generate([], {})


def test_openai_client_requires_nonempty_key():
    with pytest.raises(ValueError, match="api_key"):
        OpenAICompatibleClient(api_key="", base_url="https://api.example.test/v1", model="gpt-test")
```

- [x] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_actions.py tests/test_llm.py -v`

Expected: FAIL with missing `harness.actions` and `harness.llm`.

- [x] **Step 3: Implement action parsing and LLM classes**

Create `src/harness/actions.py`. `parse_action` must accept either a dict or JSON string, validate required `type` and `payload`, normalize `type` through `ActionType`, and raise `ValueError("unknown action type: ...")` for unknown types.

Create `src/harness/llm.py`. Use `typing.Protocol` for `LLMClient`. `MockLLMClient.generate` must pop the next script item and return JSON text. `OpenAICompatibleClient.generate` may use `httpx.Client` for a single `POST` to `{base_url}/chat/completions`; keep this method untested against network in this task. Validate `api_key`, `base_url`, and `model` are nonempty in `__init__`.

- [x] **Step 4: Run tests and lint**

Run: `pytest tests/test_actions.py tests/test_llm.py -v`

Expected: PASS.

Run: `ruff check src tests`

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add src/harness/actions.py src/harness/llm.py tests/test_actions.py tests/test_llm.py
git commit -m "feat: add action parsing and mockable llm clients"
```

---

### Task 3: Path Fence Governance

**Files:**
- Create: `src/harness/governance/__init__.py`
- Create: `src/harness/governance/path_fence.py`
- Create: `tests/governance/test_path_fence.py`

**Interfaces:**
- Consumes: `Action`, `ActionType`.
- Produces:
  - `PathFence(workspace_root: Path | str)`
  - `PathFence.resolve(candidate: Path | str) -> Path`
  - `PathFence.check_action(action: Action) -> RiskDecision`
  - `PathFenceError(ValueError)`

- [x] **Step 1: Write failing path fence tests**

Create `tests/governance/test_path_fence.py`:

```python
from pathlib import Path

from harness.models import Action, ActionType, RiskLevel
from harness.governance.path_fence import PathFence


def test_allows_workspace_relative_write(tmp_path):
    fence = PathFence(tmp_path)
    action = Action(type=ActionType.WRITE_FILE, payload={"path": "src/app.py", "content": "print('ok')"})

    decision = fence.check_action(action)

    assert decision.level == RiskLevel.ALLOW
    assert decision.reasons == ["path is inside workspace"]


def test_denies_parent_directory_escape(tmp_path):
    fence = PathFence(tmp_path)
    action = Action(type=ActionType.READ_FILE, payload={"path": "../secret.txt"})

    decision = fence.check_action(action)

    assert decision.level == RiskLevel.DENY
    assert "outside workspace" in decision.reasons[0]


def test_denies_env_file_read(tmp_path):
    fence = PathFence(tmp_path)
    action = Action(type=ActionType.READ_FILE, payload={"path": ".env"})

    decision = fence.check_action(action)

    assert decision.level == RiskLevel.DENY
    assert "sensitive credential file" in decision.reasons[0]


def test_reviews_git_directory_write(tmp_path):
    fence = PathFence(tmp_path)
    action = Action(type=ActionType.WRITE_FILE, payload={"path": ".git/config", "content": "x"})

    decision = fence.check_action(action)

    assert decision.level == RiskLevel.REVIEW
    assert "git metadata" in decision.reasons[0]
```

- [x] **Step 2: Run tests to verify failure**

Run: `pytest tests/governance/test_path_fence.py -v`

Expected: FAIL with missing `harness.governance.path_fence`.

- [x] **Step 3: Implement path fence**

Create `src/harness/governance/path_fence.py`. Resolve candidate paths using `Path.resolve(strict=False)`. Treat paths outside the resolved workspace as `DENY`. Treat file names `.env`, `.env.local`, `.npmrc`, `.pypirc`, `id_rsa`, and `id_ed25519` as `DENY`. Treat paths under `.git/` as `REVIEW`. Return `ALLOW` for read/write paths inside workspace that are not sensitive.

- [x] **Step 4: Run tests and lint**

Run: `pytest tests/governance/test_path_fence.py -v`

Expected: PASS.

Run: `ruff check src tests`

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add src/harness/governance/__init__.py src/harness/governance/path_fence.py tests/governance/test_path_fence.py
git commit -m "feat: add workspace path fence governance"
```

---

### Task 4: Command Risk Classifier

**Files:**
- Create: `src/harness/governance/risk.py`
- Create: `tests/governance/test_risk.py`

**Interfaces:**
- Consumes: `Action`, `ActionType`, `RiskDecision`, `RiskLevel`.
- Produces:
  - `RiskClassifier.classify(action: Action) -> RiskDecision`

- [x] **Step 1: Write failing risk classifier tests**

Create `tests/governance/test_risk.py`:

```python
from harness.governance.risk import RiskClassifier
from harness.models import Action, ActionType, RiskLevel


def classify(command: str):
    action = Action(type=ActionType.RUN_COMMAND, payload={"command": command})
    return RiskClassifier().classify(action)


def test_allows_pytest_and_ruff():
    assert classify("pytest").level == RiskLevel.ALLOW
    assert classify("ruff check src tests").level == RiskLevel.ALLOW


def test_reviews_git_push_and_dependency_install():
    assert classify("git push origin main").level == RiskLevel.REVIEW
    assert classify("pip install requests").level == RiskLevel.REVIEW


def test_reviews_long_running_server_commands():
    assert classify("uvicorn harness.web:app --host 0.0.0.0").level == RiskLevel.REVIEW


def test_denies_destructive_or_secret_commands():
    assert classify("rm -rf /").level == RiskLevel.DENY
    assert classify("cat .env").level == RiskLevel.DENY
    assert classify("psql -c 'DROP DATABASE prod'").level == RiskLevel.DENY


def test_non_command_actions_default_allow():
    action = Action(type=ActionType.REQUEST_DONE, payload={"summary": "done"})

    decision = RiskClassifier().classify(action)

    assert decision.level == RiskLevel.ALLOW
```

- [x] **Step 2: Run tests to verify failure**

Run: `pytest tests/governance/test_risk.py -v`

Expected: FAIL with missing `harness.governance.risk`.

- [x] **Step 3: Implement classifier**

Create `src/harness/governance/risk.py`. Use `shlex.split(command, posix=False)` and lowercase pattern checks. Deny commands containing destructive database terms (`drop database`, `truncate table`), secret file reads (`.env`, `.npmrc`, `.pypirc`, `id_rsa`, `id_ed25519`), or destructive root deletion (`rm -rf /`, `del /s`, `format`). Review commands starting with `git push`, `pip install`, `npm install`, `poetry add`, `curl`, `wget`, `uvicorn`, `python -m http.server`, or containing `--host 0.0.0.0`. Allow `pytest`, `python -m pytest`, `ruff`, `git status`, and `git diff`.

- [x] **Step 4: Run tests and lint**

Run: `pytest tests/governance/test_risk.py -v`

Expected: PASS.

Run: `ruff check src tests`

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add src/harness/governance/risk.py tests/governance/test_risk.py
git commit -m "feat: classify command risk deterministically"
```

---

### Task 5: HITL Approval Store And State Machine

**Files:**
- Create: `src/harness/governance/approval.py`
- Create: `tests/governance/test_approval.py`

**Interfaces:**
- Consumes: `Action`, `ApprovalRequest`, `ApprovalStatus`, `RiskDecision`.
- Produces:
  - `JsonApprovalStore(path: Path | str)`
  - `JsonApprovalStore.create(action: Action, risk_decision: RiskDecision) -> ApprovalRequest`
  - `JsonApprovalStore.get(request_id: str) -> ApprovalRequest`
  - `JsonApprovalStore.list(status: ApprovalStatus | None = None) -> list[ApprovalRequest]`
  - `JsonApprovalStore.resolve(request_id: str, status: ApprovalStatus, note: str = "") -> ApprovalRequest`
  - `ApprovalStateMachine.approve(request_id: str, note: str = "") -> ApprovalRequest`
  - `ApprovalStateMachine.reject(request_id: str, note: str = "") -> ApprovalRequest`
  - `ApprovalStateMachine.expire(request_id: str, note: str = "expired") -> ApprovalRequest`

- [x] **Step 1: Write failing approval tests**

Create `tests/governance/test_approval.py`:

```python
import pytest

from harness.governance.approval import ApprovalStateMachine, JsonApprovalStore
from harness.models import Action, ActionType, ApprovalStatus, RiskDecision, RiskLevel


def make_review_action():
    action = Action(type=ActionType.RUN_COMMAND, payload={"command": "git push"})
    decision = RiskDecision(level=RiskLevel.REVIEW, reasons=["publishes external state"])
    return action, decision


def test_create_and_reload_pending_approval(tmp_path):
    store = JsonApprovalStore(tmp_path / "approvals.json")
    action, decision = make_review_action()

    request = store.create(action, decision)
    reloaded = JsonApprovalStore(tmp_path / "approvals.json").get(request.id)

    assert reloaded.status == ApprovalStatus.PENDING
    assert reloaded.action.payload["command"] == "git push"


def test_approve_reject_expire_transitions(tmp_path):
    store = JsonApprovalStore(tmp_path / "approvals.json")
    machine = ApprovalStateMachine(store)

    approved = store.create(*make_review_action())
    rejected = store.create(*make_review_action())
    expired = store.create(*make_review_action())

    assert machine.approve(approved.id).status == ApprovalStatus.APPROVED
    assert machine.reject(rejected.id).status == ApprovalStatus.REJECTED
    assert machine.expire(expired.id).status == ApprovalStatus.EXPIRED


def test_cannot_resolve_non_pending_request_twice(tmp_path):
    store = JsonApprovalStore(tmp_path / "approvals.json")
    machine = ApprovalStateMachine(store)
    request = store.create(*make_review_action())
    machine.reject(request.id)

    with pytest.raises(ValueError, match="not pending"):
        machine.approve(request.id)
```

- [x] **Step 2: Run tests to verify failure**

Run: `pytest tests/governance/test_approval.py -v`

Expected: FAIL with missing `harness.governance.approval`.

- [x] **Step 3: Implement JSON approval persistence**

Create `src/harness/governance/approval.py`. Store a JSON list of Pydantic-serialized `ApprovalRequest` objects. Use atomic write via `path.with_suffix(".tmp")` then `replace`. If the JSON file does not exist, treat it as an empty list. If resolving a non-pending request, raise `ValueError("approval request is not pending")`.

- [x] **Step 4: Run tests and lint**

Run: `pytest tests/governance/test_approval.py -v`

Expected: PASS.

Run: `ruff check src tests`

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add src/harness/governance/approval.py tests/governance/test_approval.py
git commit -m "feat: add hitl approval state machine"
```

---

### Task 6: JSON Memory Store

**Files:**
- Create: `src/harness/memory.py`
- Create: `tests/test_memory.py`

**Interfaces:**
- Consumes: `MemoryEntry`, `MemoryKind`.
- Produces:
  - `MemoryStore` protocol with `add(entry: MemoryEntry) -> MemoryEntry` and `search(query: str, kinds: set[MemoryKind] | None = None, limit: int = 5) -> list[MemoryEntry]`
  - `JsonMemoryStore(path: Path | str)`
  - `MySQLMemoryStore` class whose constructor raises `NotImplementedError("MySQLMemoryStore is reserved for a future adapter")`

- [x] **Step 1: Write failing memory tests**

Create `tests/test_memory.py`:

```python
import json

import pytest

from harness.memory import JsonMemoryStore, MySQLMemoryStore
from harness.models import MemoryEntry, MemoryKind


def test_add_and_search_memory_by_keyword(tmp_path):
    store = JsonMemoryStore(tmp_path / "memory.json")
    store.add(MemoryEntry(kind=MemoryKind.CONVENTION, text="Do not use SQLite", keywords=["memory", "json"]))
    store.add(MemoryEntry(kind=MemoryKind.DECISION, text="Governance is the main contribution", keywords=["governance"]))

    results = store.search("memory json", limit=1)

    assert len(results) == 1
    assert results[0].text == "Do not use SQLite"


def test_search_filters_by_kind(tmp_path):
    store = JsonMemoryStore(tmp_path / "memory.json")
    store.add(MemoryEntry(kind=MemoryKind.CONVENTION, text="Use JSON memory", keywords=["memory"]))
    store.add(MemoryEntry(kind=MemoryKind.FAILURE_SUMMARY, text="pytest failed", keywords=["memory"]))

    results = store.search("memory", kinds={MemoryKind.FAILURE_SUMMARY})

    assert [item.kind for item in results] == [MemoryKind.FAILURE_SUMMARY]


def test_corrupt_memory_file_is_backed_up(tmp_path):
    path = tmp_path / "memory.json"
    path.write_text("{broken", encoding="utf-8")

    with pytest.raises(ValueError, match="memory file is not valid JSON"):
        JsonMemoryStore(path).search("anything")

    assert (tmp_path / "memory.json.bak").exists()


def test_memory_file_never_contains_api_key_marker(tmp_path):
    store = JsonMemoryStore(tmp_path / "memory.json")
    store.add(MemoryEntry(kind=MemoryKind.DECISION, text="OPENAI_API_KEY=sk-secret", keywords=["secret"]))

    raw = json.loads((tmp_path / "memory.json").read_text(encoding="utf-8"))

    assert "sk-secret" not in json.dumps(raw)
    assert "[redacted]" in json.dumps(raw)


def test_mysql_adapter_is_explicitly_future_work():
    with pytest.raises(NotImplementedError, match="future adapter"):
        MySQLMemoryStore()
```

- [x] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_memory.py -v`

Expected: FAIL with missing `harness.memory`.

- [x] **Step 3: Implement JSON memory**

Create `src/harness/memory.py`. Serialize a JSON list of `MemoryEntry` objects. Search by scoring one point per query token found in `text.lower()` or `keywords`; sort by score descending, then `created_at` descending. Redact secret-looking substrings before writing: replace `sk-` followed by at least 8 alphanumeric characters, and `OPENAI_API_KEY=...`, with `[redacted]`. On JSON decode failure, copy the corrupt file to `.bak` and raise `ValueError("memory file is not valid JSON")`.

- [x] **Step 4: Run tests and lint**

Run: `pytest tests/test_memory.py -v`

Expected: PASS.

Run: `ruff check src tests`

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add src/harness/memory.py tests/test_memory.py
git commit -m "feat: add json memory store"
```

---

### Task 7: Feedback Parsers

**Files:**
- Create: `src/harness/feedback.py`
- Create: `tests/test_feedback.py`

**Interfaces:**
- Consumes: `ToolResult`, `Feedback`.
- Produces:
  - `parse_feedback(result: ToolResult) -> Feedback`
  - `parse_pytest_failure(result: ToolResult) -> Feedback | None`
  - `parse_ruff_failure(result: ToolResult) -> Feedback | None`
  - `parse_command_failure(result: ToolResult) -> Feedback`

- [x] **Step 1: Write failing feedback tests**

Create `tests/test_feedback.py`:

```python
from harness.feedback import parse_feedback
from harness.models import ToolResult


def test_parse_pytest_failure_summary():
    stderr = ""
    stdout = """
    FAILED tests/test_math.py::test_add - assert 3 == 4
    E       assert 3 == 4
    """
    result = ToolResult(action_id="act_pytest", ok=False, stdout=stdout, stderr=stderr, exit_code=1)

    feedback = parse_feedback(result)

    assert feedback.kind == "pytest_failure"
    assert "tests/test_math.py::test_add" in feedback.summary
    assert feedback.details["exit_code"] == 1


def test_parse_ruff_failure_summary():
    stdout = "src/app.py:3:1: F401 `os` imported but unused\nFound 1 error."
    result = ToolResult(action_id="act_ruff", ok=False, stdout=stdout, stderr="", exit_code=1)

    feedback = parse_feedback(result)

    assert feedback.kind == "ruff_failure"
    assert feedback.details["rule"] == "F401"
    assert feedback.details["file"] == "src/app.py"
    assert feedback.details["line"] == 3


def test_parse_timeout_as_command_failure():
    result = ToolResult(action_id="act_cmd", ok=False, stdout="", stderr="", exit_code=None, timed_out=True)

    feedback = parse_feedback(result)

    assert feedback.kind == "command_timeout"
    assert "timed out" in feedback.summary
```

- [x] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_feedback.py -v`

Expected: FAIL with missing `harness.feedback`.

- [x] **Step 3: Implement parsers**

Create `src/harness/feedback.py`. Detect pytest failures by `FAILED ` lines and include the first failure node id. Detect ruff failures using regex `^(.+?):(\d+):(\d+): ([A-Z]\d+) (.+)$`. If `timed_out` is true, return `Feedback(kind="command_timeout", ...)`. Otherwise return `Feedback(kind="command_failure", ...)` with exit code and first 1000 characters of stderr/stdout.

- [x] **Step 4: Run tests and lint**

Run: `pytest tests/test_feedback.py -v`

Expected: PASS.

Run: `ruff check src tests`

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add src/harness/feedback.py tests/test_feedback.py
git commit -m "feat: parse structured command feedback"
```

---

### Task 8: Tool Executor With File And Command Actions

**Files:**
- Create: `src/harness/tools.py`
- Create: `tests/test_tools.py`

**Interfaces:**
- Consumes: `Action`, `ActionType`, `ToolResult`, `PathFence`.
- Produces:
  - `ToolExecutor(workspace_root: Path | str, default_timeout_seconds: float = 10.0)`
  - `ToolExecutor.execute(action: Action) -> ToolResult`

- [x] **Step 1: Write failing tool tests**

Create `tests/test_tools.py`:

```python
from harness.models import Action, ActionType
from harness.tools import ToolExecutor


def test_write_and_read_file_inside_workspace(tmp_path):
    executor = ToolExecutor(tmp_path)
    write = Action(type=ActionType.WRITE_FILE, payload={"path": "hello.txt", "content": "hello"})
    read = Action(type=ActionType.READ_FILE, payload={"path": "hello.txt"})

    write_result = executor.execute(write)
    read_result = executor.execute(read)

    assert write_result.ok is True
    assert read_result.ok is True
    assert read_result.stdout == "hello"


def test_run_command_uses_workspace_and_exit_code(tmp_path):
    executor = ToolExecutor(tmp_path)
    action = Action(type=ActionType.RUN_COMMAND, payload={"command": "python -c \"print('ok')\""})

    result = executor.execute(action)

    assert result.ok is True
    assert result.exit_code == 0
    assert result.stdout.strip() == "ok"


def test_run_command_timeout(tmp_path):
    executor = ToolExecutor(tmp_path, default_timeout_seconds=0.1)
    action = Action(type=ActionType.RUN_COMMAND, payload={"command": "python -c \"import time; time.sleep(2)\""})

    result = executor.execute(action)

    assert result.ok is False
    assert result.timed_out is True
```

- [x] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_tools.py -v`

Expected: FAIL with missing `harness.tools`.

- [x] **Step 3: Implement executor**

Create `src/harness/tools.py`. Use `PathFence.resolve` for file paths. For `RUN_COMMAND`, use `subprocess.run(command, shell=True, cwd=workspace_root, capture_output=True, text=True, timeout=timeout_seconds)`. Catch `subprocess.TimeoutExpired` and return `ToolResult(ok=False, timed_out=True, exit_code=None, stdout=exc.stdout or "", stderr=exc.stderr or "")`. Support `RUN_CHECKS` by running `pytest` and then `ruff check src tests`, returning the first failing result or a combined success result.

- [x] **Step 4: Run tests and lint**

Run: `pytest tests/test_tools.py -v`

Expected: PASS.

Run: `ruff check src tests`

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add src/harness/tools.py tests/test_tools.py
git commit -m "feat: execute governed file and command tools"
```

---

### Task 9: Config And Credential Handling

**Files:**
- Create: `src/harness/config.py`
- Create: `src/harness/credentials.py`
- Create: `tests/test_config.py`
- Create: `tests/test_credentials.py`

**Interfaces:**
- Consumes: `CredentialStatus`.
- Produces:
  - `HarnessConfig(workspace_root: Path, llm_provider: str = "openai-compatible", default_timeout_seconds: float = 10.0, max_iterations: int = 8)`
  - `HarnessConfig.paths() -> dict[str, Path]`
  - `mask_secret(value: str) -> str`
  - `CredentialManager(service_name: str = "coding-agent-harness")`
  - `CredentialManager.status(provider: str = "openai") -> CredentialStatus`
  - `CredentialManager.get_api_key(provider: str = "openai") -> str | None`
  - `CredentialManager.set_api_key(api_key: str, provider: str = "openai") -> None`
  - `CredentialManager.clear_api_key(provider: str = "openai") -> None`

- [x] **Step 1: Write failing config and credential tests**

Create `tests/test_config.py`:

```python
from harness.config import HarnessConfig


def test_config_creates_harness_paths(tmp_path):
    config = HarnessConfig(workspace_root=tmp_path)

    paths = config.paths()

    assert paths["state_dir"] == tmp_path / ".harness"
    assert paths["memory"] == tmp_path / ".harness" / "memory.json"
    assert paths["approvals"] == tmp_path / ".harness" / "approvals.json"
```

Create `tests/test_credentials.py`:

```python
from harness.credentials import CredentialManager, mask_secret


class FakeKeyring:
    def __init__(self):
        self.values = {}

    def get_password(self, service, username):
        return self.values.get((service, username))

    def set_password(self, service, username, password):
        self.values[(service, username)] = password

    def delete_password(self, service, username):
        self.values.pop((service, username), None)


def test_mask_secret_never_returns_plaintext():
    assert mask_secret("sk-abcdefghijklmnopqrstuvwxyz") == "sk-a...wxyz"
    assert mask_secret("") == ""


def test_credential_manager_uses_keyring(monkeypatch):
    fake = FakeKeyring()
    monkeypatch.setattr("harness.credentials.keyring", fake)
    manager = CredentialManager(service_name="test-harness")

    manager.set_api_key("sk-abcdefghijklmnopqrstuvwxyz")

    assert manager.get_api_key() == "sk-abcdefghijklmnopqrstuvwxyz"
    status = manager.status()
    assert status.exists is True
    assert status.masked_preview == "sk-a...wxyz"
```

- [x] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_config.py tests/test_credentials.py -v`

Expected: FAIL with missing modules.

- [x] **Step 3: Implement config and credentials**

Create `src/harness/config.py` using Pydantic `BaseModel` with `workspace_root: Path`. `paths()` returns `state_dir`, `runs_dir`, `approvals`, `memory`, and `logs_dir`.

Create `src/harness/credentials.py`. `mask_secret` returns first four characters, ellipsis, and last four characters for values longer than 10. `CredentialManager.get_api_key` checks keyring first, then environment variable `OPENAI_API_KEY`. `status()` returns source `"keyring"`, `"env"`, or `"missing"` without plaintext.

- [x] **Step 4: Run tests and lint**

Run: `pytest tests/test_config.py tests/test_credentials.py -v`

Expected: PASS.

Run: `ruff check src tests`

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add src/harness/config.py src/harness/credentials.py tests/test_config.py tests/test_credentials.py
git commit -m "feat: add safe config and credential handling"
```

---

### Task 10: Agent Loop Integration

**Files:**
- Create: `src/harness/core/__init__.py`
- Create: `src/harness/core/loop.py`
- Create: `tests/core/test_loop.py`

**Interfaces:**
- Consumes: `parse_action`, `LLMClient`, `MockLLMClient`, `RiskClassifier`, `PathFence`, `JsonApprovalStore`, `JsonMemoryStore`, `ToolExecutor`, `parse_feedback`, `HarnessConfig`.
- Produces:
  - `AgentLoop(config: HarnessConfig, llm: LLMClient, approval_store: JsonApprovalStore | None = None, memory_store: MemoryStore | None = None, tool_executor: ToolExecutor | None = None)`
  - `AgentLoop.run(task: str) -> TaskRun`
  - `AgentLoop.resume(run_id: str) -> TaskRun`

- [x] **Step 1: Write failing loop integration tests**

Create `tests/core/test_loop.py`:

```python
from harness.config import HarnessConfig
from harness.core.loop import AgentLoop
from harness.llm import MockLLMClient
from harness.models import RunStatus


def test_loop_denies_dangerous_action_without_execution(tmp_path):
    llm = MockLLMClient([
        {"type": "run_command", "payload": {"command": "rm -rf /"}},
    ])
    loop = AgentLoop(HarnessConfig(workspace_root=tmp_path, max_iterations=1), llm)

    run = loop.run("try dangerous command")

    assert run.status == RunStatus.FAILED
    assert run.stop_reason == "denied_by_governance"
    assert not (tmp_path / "should_not_exist").exists()


def test_loop_waits_for_review_action(tmp_path):
    llm = MockLLMClient([
        {"type": "run_command", "payload": {"command": "git push origin main"}},
    ])
    loop = AgentLoop(HarnessConfig(workspace_root=tmp_path, max_iterations=1), llm)

    run = loop.run("publish branch")

    assert run.status == RunStatus.WAITING_FOR_APPROVAL
    assert run.stop_reason == "approval_required"


def test_loop_runs_feedback_repair_script(tmp_path):
    (tmp_path / "calc.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    (tmp_path / "test_calc.py").write_text(
        "from calc import add\n\n"
        "def test_add():\n"
        "    assert add(2, 2) == 4\n",
        encoding="utf-8",
    )
    llm = MockLLMClient([
        {"type": "run_command", "payload": {"command": "pytest -q"}},
        {"type": "write_file", "payload": {"path": "calc.py", "content": "def add(a, b):\n    return a + b\n"}},
        {"type": "run_command", "payload": {"command": "pytest -q"}},
        {"type": "request_done", "payload": {"summary": "fixed add"}},
    ])
    loop = AgentLoop(HarnessConfig(workspace_root=tmp_path, max_iterations=6), llm)

    run = loop.run("fix failing test")

    assert run.status == RunStatus.COMPLETED
    assert run.stop_reason == "request_done"
```

- [x] **Step 2: Run tests to verify failure**

Run: `pytest tests/core/test_loop.py -v`

Expected: FAIL with missing `harness.core.loop`.

- [x] **Step 3: Implement the self-owned loop**

Create `src/harness/core/loop.py`. For each iteration:

1. Build messages with task text, recent feedback summaries, and memory search results.
2. Call `llm.generate(messages, build_action_schema())`.
3. Parse the action.
4. Run `PathFence.check_action` for file actions and `RiskClassifier.classify` for command actions.
5. If `DENY`, append feedback and stop with `RunStatus.FAILED`, `stop_reason="denied_by_governance"`.
6. If `REVIEW`, create approval request and stop with `RunStatus.WAITING_FOR_APPROVAL`, `stop_reason="approval_required"`.
7. If action is `REMEMBER`, write memory and continue.
8. If action is `REQUEST_DONE`, stop with `RunStatus.COMPLETED`, `stop_reason="request_done"`.
9. Otherwise execute tool, parse failed tool results into feedback, and continue.
10. If loop exhausts iterations, stop with `RunStatus.MAX_ITERATIONS`.

Persist `.harness/runs/<run_id>.json` after each iteration.

- [x] **Step 4: Run tests and lint**

Run: `pytest tests/core/test_loop.py -v`

Expected: PASS.

Run: `pytest -q`

Expected: PASS.

Run: `ruff check src tests`

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add src/harness/core/__init__.py src/harness/core/loop.py tests/core/test_loop.py
git commit -m "feat: integrate self-owned agent loop"
```

---

### Task 11: CLI Commands

**Files:**
- Create: `src/harness/cli.py`
- Create: `tests/test_cli.py`

**Interfaces:**
- Consumes: `AgentLoop`, `HarnessConfig`, `MockLLMClient`, `JsonApprovalStore`, `ApprovalStateMachine`, `CredentialManager`, `JsonMemoryStore`.
- Produces Typer app with commands:
  - `harness run TASK --workspace PATH --mock-script PATH`
  - `harness demo --workspace PATH`
  - `harness approvals list --workspace PATH`
  - `harness approvals approve REQUEST_ID --workspace PATH`
  - `harness approvals reject REQUEST_ID --workspace PATH`
  - `harness credentials status`
  - `harness credentials set`
  - `harness credentials clear`
  - `harness memory list --workspace PATH`

- [x] **Step 1: Write failing CLI tests**

Create `tests/test_cli.py`:

```python
import json

from typer.testing import CliRunner

from harness.cli import app


runner = CliRunner()


def test_demo_runs_without_api_key(tmp_path):
    result = runner.invoke(app, ["demo", "--workspace", str(tmp_path)])

    assert result.exit_code == 0
    assert "COMPLETED" in result.stdout


def test_run_accepts_mock_script(tmp_path):
    script = tmp_path / "script.json"
    script.write_text(json.dumps([
        {"type": "request_done", "payload": {"summary": "done"}}
    ]), encoding="utf-8")

    result = runner.invoke(app, ["run", "finish", "--workspace", str(tmp_path), "--mock-script", str(script)])

    assert result.exit_code == 0
    assert "request_done" in result.stdout


def test_credentials_status_does_not_show_plaintext(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-abcdefghijklmnopqrstuvwxyz")

    result = runner.invoke(app, ["credentials", "status"])

    assert result.exit_code == 0
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in result.stdout
    assert "sk-a...wxyz" in result.stdout
```

- [x] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_cli.py -v`

Expected: FAIL with missing `harness.cli` or command definitions.

- [x] **Step 3: Implement CLI**

Create `src/harness/cli.py` with Typer. The `demo` command must create a deterministic mock script that writes a tiny passing file or requests done, then prints final status. The `run` command must load `--mock-script` JSON and use `MockLLMClient`; if no mock script is provided, it must attempt credentials and instantiate `OpenAICompatibleClient`. Approval commands use `JsonApprovalStore(config.paths()["approvals"])`. Credential commands never print plaintext.

- [x] **Step 4: Run tests and lint**

Run: `pytest tests/test_cli.py -v`

Expected: PASS.

Run: `pytest -q`

Expected: PASS.

Run: `ruff check src tests`

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add src/harness/cli.py tests/test_cli.py
git commit -m "feat: expose harness cli commands"
```

---

### Task 12: Minimal WebUI And API

**Files:**
- Create: `src/harness/web.py`
- Create: `tests/test_web.py`

**Interfaces:**
- Consumes: `HarnessConfig`, `JsonApprovalStore`, `ApprovalStateMachine`, `JsonMemoryStore`.
- Produces:
  - `create_app(workspace_root: str | Path) -> FastAPI`
  - Routes: `GET /`, `GET /api/approvals`, `POST /api/approvals/{request_id}/approve`, `POST /api/approvals/{request_id}/reject`, `GET /api/memory`, `GET /api/runs`

- [x] **Step 1: Write failing WebUI tests**

Create `tests/test_web.py`:

```python
from fastapi.testclient import TestClient

from harness.governance.approval import JsonApprovalStore
from harness.models import Action, ActionType, RiskDecision, RiskLevel
from harness.web import create_app


def test_home_page_contains_status_sections(tmp_path):
    client = TestClient(create_app(tmp_path))

    response = client.get("/")

    assert response.status_code == 200
    assert "Task Status" in response.text
    assert "Approval Queue" in response.text
    assert "Memory" in response.text


def test_approval_api_lists_and_approves(tmp_path):
    store = JsonApprovalStore(tmp_path / ".harness" / "approvals.json")
    request = store.create(
        Action(type=ActionType.RUN_COMMAND, payload={"command": "git push"}),
        RiskDecision(level=RiskLevel.REVIEW, reasons=["publishes external state"]),
    )
    client = TestClient(create_app(tmp_path))

    listed = client.get("/api/approvals").json()
    approved = client.post(f"/api/approvals/{request.id}/approve").json()

    assert listed[0]["id"] == request.id
    assert approved["status"] == "approved"
```

- [x] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_web.py -v`

Expected: FAIL with missing `harness.web`.

- [x] **Step 3: Implement FastAPI app**

Create `src/harness/web.py`. `GET /` may return a small HTML string with four sections: `Task Status`, `Approval Queue`, `Recent Feedback`, and `Memory`. API routes read and update the same `.harness/approvals.json` and `.harness/memory.json` stores used by CLI. WebUI must not execute shell commands or call tools.

- [x] **Step 4: Run tests and lint**

Run: `pytest tests/test_web.py -v`

Expected: PASS.

Run: `pytest -q`

Expected: PASS.

Run: `ruff check src tests`

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add src/harness/web.py tests/test_web.py
git commit -m "feat: add minimal web approval ui"
```

---

### Task 13: Deterministic Mechanism Demo

**Files:**
- Create: `examples/mock_project/calc.py`
- Create: `examples/mock_project/test_calc.py`
- Create: `scripts/mock_demo.py`
- Create: `tests/test_demo.py`

**Interfaces:**
- Consumes: `AgentLoop`, `HarnessConfig`, `MockLLMClient`.
- Produces:
  - `scripts/mock_demo.py`
  - `run_demo(workspace: Path) -> dict[str, str]`

- [x] **Step 1: Write failing demo test**

Create `tests/test_demo.py`:

```python
from scripts.mock_demo import run_demo


def test_mock_demo_covers_required_mechanisms(tmp_path):
    summary = run_demo(tmp_path)

    assert summary["dangerous_action"] == "denied_by_governance"
    assert summary["feedback_repair"] == "completed"
    assert summary["hitl"] == "waiting_for_approval"
```

- [x] **Step 2: Run test to verify failure**

Run: `pytest tests/test_demo.py -v`

Expected: FAIL with missing `scripts.mock_demo`.

- [x] **Step 3: Implement mock demo**

Create `scripts/mock_demo.py` with `run_demo(workspace: Path) -> dict[str, str]`. It must run three independent mock scenarios:

1. Dangerous action: mock LLM returns `run_command rm -rf /`; assert loop stop reason is `denied_by_governance`.
2. Feedback repair: create `calc.py` with bad addition and `test_calc.py`; mock LLM runs pytest, writes fixed file, runs pytest, requests done.
3. HITL: mock LLM returns `git push origin main`; assert loop status is `WAITING_FOR_APPROVAL`.

When executed as a script, print one line per scenario:

```text
dangerous_action=denied_by_governance
feedback_repair=completed
hitl=waiting_for_approval
```

- [x] **Step 4: Run demo tests and command**

Run: `pytest tests/test_demo.py -v`

Expected: PASS.

Run: `python scripts/mock_demo.py`

Expected: prints all three scenario lines exactly once.

Run: `ruff check src tests scripts`

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add examples/mock_project/calc.py examples/mock_project/test_calc.py scripts/mock_demo.py tests/test_demo.py
git commit -m "test: add deterministic mock mechanism demo"
```

---

### Task 14: Docker, CI, And Distribution Commands

**Files:**
- Create: `Dockerfile`
- Create: `.gitlab-ci.yml`
- Modify: `Makefile`
- Create: `tests/test_distribution_files.py`

**Interfaces:**
- Consumes: project package and CLI.
- Produces:
  - Docker image that can run `harness demo --workspace /workspace`
  - GitLab CI job `unit-test`
  - GitLab CI job `docker-build`

- [x] **Step 1: Write failing distribution file tests**

Create `tests/test_distribution_files.py`:

```python
from pathlib import Path


def test_gitlab_ci_contains_required_unit_test_job():
    text = Path(".gitlab-ci.yml").read_text(encoding="utf-8")

    assert "unit-test:" in text
    assert "pytest" in text


def test_dockerfile_runs_harness_cli():
    text = Path("Dockerfile").read_text(encoding="utf-8")

    assert "python:3.11" in text
    assert "pip install" in text
    assert "harness" in text


def test_makefile_exposes_required_commands():
    text = Path("Makefile").read_text(encoding="utf-8")

    assert "test:" in text
    assert "lint:" in text
    assert "demo:" in text
```

- [x] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_distribution_files.py -v`

Expected: FAIL because `Dockerfile` and `.gitlab-ci.yml` do not exist.

- [x] **Step 3: Add Dockerfile and CI**

Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY scripts ./scripts
RUN pip install --no-cache-dir .[dev]

RUN mkdir -p /workspace
WORKDIR /workspace
EXPOSE 8000
CMD ["harness", "demo", "--workspace", "/workspace"]
```

Create `.gitlab-ci.yml`:

```yaml
stages:
  - test
  - build

unit-test:
  stage: test
  image: python:3.11
  script:
    - pip install .[dev]
    - pytest -q
    - ruff check src tests scripts

docker-build:
  stage: build
  image: docker:27
  services:
    - docker:27-dind
  script:
    - docker build -t coding-agent-harness:ci .
```

If `Makefile` lacks any of `test`, `lint`, or `demo`, add them exactly as in Task 1.

- [x] **Step 4: Run verification commands**

Run: `pytest tests/test_distribution_files.py -v`

Expected: PASS.

Run: `pytest -q`

Expected: PASS.

Run: `ruff check src tests scripts`

Expected: PASS.

Run: `docker build -t coding-agent-harness:local .`

Expected: image builds successfully.

- [x] **Step 5: Commit**

```bash
git add Dockerfile .gitlab-ci.yml Makefile tests/test_distribution_files.py
git commit -m "chore: add docker and gitlab ci distribution"
```

---

### Task 15: Course Documents And Final Verification

**Files:**
- Create: `SPEC.md`
- Create: `PLAN.md`
- Create: `SPEC_PROCESS.md`
- Create: `AGENT_LOG.md`
- Create: `REFLECTION.md`
- Modify: `README.md`
- Create: `tests/test_docs.py`

**Interfaces:**
- Consumes: confirmed design spec, this implementation plan, project commands.
- Produces course-ready root documents and README sections.

- [x] **Step 1: Write failing documentation tests**

Create `tests/test_docs.py`:

```python
from pathlib import Path


REQUIRED_README_SECTIONS = [
    "## Installation",
    "## Usage",
    "## Docker Distribution",
    "## API Key Security",
    "## Directory Structure",
    "## Security Boundaries",
]


def test_required_course_documents_exist():
    for name in ["SPEC.md", "PLAN.md", "SPEC_PROCESS.md", "AGENT_LOG.md", "REFLECTION.md", "README.md"]:
        assert Path(name).exists(), f"{name} is missing"


def test_readme_contains_required_sections():
    text = Path("README.md").read_text(encoding="utf-8")

    for section in REQUIRED_README_SECTIONS:
        assert section in text


def test_plan_mentions_tdd_and_mock_llm():
    text = Path("PLAN.md").read_text(encoding="utf-8")

    assert "TDD" in text
    assert "mock LLM" in text
```

- [x] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_docs.py -v`

Expected: FAIL because root course documents are missing or incomplete.

- [x] **Step 3: Create and update documentation**

Create `SPEC.md` by adapting `docs/superpowers/specs/2026-08-10-coding-agent-harness-design.md` into the required root SPEC format. It must include problem statement, user stories, functional spec, non-functional requirements, architecture, data model, credential and distribution design, technology choices, acceptance criteria, risks, and the A-project “领域与机制设计” section.

Create `PLAN.md` by copying this plan from `docs/superpowers/plans/2026-08-10-coding-agent-harness.md` and updating task checkboxes as tasks complete.

Create `SPEC_PROCESS.md` with sections:

```markdown
# SPEC Process

## Brainstorming Key Nodes

## Three Critical Iterations

## Adopted AI Suggestions

## Rejected Or Revised AI Suggestions

## Cold-Start Trial Record

## Reflection On Brainstorming
```

Create `AGENT_LOG.md` with a chronological table:

```markdown
# Agent Log

| Time | Task | Superpowers Skill | Context / Prompt | Output / Commit | Human Intervention |
| --- | --- | --- | --- | --- | --- |
```

Create `REFLECTION.md` with headings only and no generated final reflection prose:

```markdown
# Reflection

## Superpowers Skills

## TDD In AI Collaboration

## Subagent Workflow

## SPEC And PLAN Quality

## Prompt And Context Strategy

## Credential And Distribution Lessons

## Critique Of Superpowers
```

Update `README.md` with the exact required sections from the test. Include Docker commands:

```bash
docker build -t coding-agent-harness:local .
docker run --rm -v "$PWD:/workspace" coding-agent-harness:local
docker run --rm -p 8000:8000 -v "$PWD:/workspace" coding-agent-harness:local uvicorn harness.web:app --host 0.0.0.0 --port 8000
```

- [ ] **Step 4: Run full verification**

Run: `pytest -q`

Expected: PASS.

Run: `ruff check src tests scripts`

Expected: PASS.

Run: `python scripts/mock_demo.py`

Expected: prints `dangerous_action=denied_by_governance`, `feedback_repair=completed`, and `hitl=waiting_for_approval`.

Run: `docker build -t coding-agent-harness:local .`

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add SPEC.md PLAN.md SPEC_PROCESS.md AGENT_LOG.md REFLECTION.md README.md tests/test_docs.py
git commit -m "docs: add course deliverables and verification notes"
```

---

## Self-Review

### Spec Coverage

- Self-owned agent loop: Task 10.
- Mockable LLM abstraction: Task 2 and Task 10.
- Action parsing and tool dispatch: Task 2 and Task 8.
- Governance guardrails: Tasks 3, 4, 5, and Task 10 integration.
- Feedback loop: Task 7 and Task 10 integration.
- JSON memory with no SQLite: Task 6.
- Credential safety: Task 9 and README work in Task 15.
- CLI primary interface: Task 11.
- Minimal WebUI: Task 12.
- Mock mechanism demo: Task 13.
- Docker distribution and CI `unit-test`: Task 14.
- Course documents: Task 15.

### Placeholder Scan

The plan contains no unspecified implementation placeholders. The `MySQLMemoryStore` is explicitly specified as a future adapter class that raises a clear `NotImplementedError`, matching the approved MVP scope.

### Type Consistency

The same public names are used throughout: `Action`, `ActionType`, `RiskDecision`, `RiskLevel`, `ToolResult`, `Feedback`, `ApprovalRequest`, `ApprovalStatus`, `MemoryEntry`, `MemoryKind`, `TaskRun`, `RunStatus`, `HarnessConfig`, `MockLLMClient`, `JsonApprovalStore`, `JsonMemoryStore`, `ToolExecutor`, and `AgentLoop`.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-10-coding-agent-harness.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?

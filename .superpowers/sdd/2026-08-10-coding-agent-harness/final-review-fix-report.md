# Final Review Fix Report

Date: 2026-08-12

Branch: `codex/coding-agent-harness`

Review base: `d2b20afe213bfe564969f264b11e9dd68b0506bc`

## Status

DONE_WITH_CONCERNS. All Critical and Important findings were fixed with regression tests. The
required non-Docker verification commands pass. Docker daemon and Buildx were not exercised in
this environment, and the test suite reports one upstream FastAPI/Starlette TestClient deprecation
warning.

## RED Evidence

The first focused run was intentionally executed after adding regression tests and before changing
production code:

```text
pytest -q -p no:cacheprovider tests/governance/test_risk.py \
  tests/governance/test_path_fence.py tests/test_tools.py tests/core/test_loop.py

14 failed, 25 passed in 3.30s
```

The failures reproduced the review findings:

- git aliases, shell wrappers, unknown commands, and non-string commands were allowed.
- `.env.production` and common cloud credential paths were allowed and readable.
- successful file output was absent from the second model prompt and persisted run state.
- malformed JSON, unknown action types, and missing payload keys escaped the loop.
- `TaskRun` had no approval association; pending resume incorrectly continued, and approved resume
  could not consume the stored action.
- importing `harness.web.app` failed during Web test collection.

Additional RED checks during hardening:

```text
test_denies_common_credential_paths_case_insensitively
FAILED for nested/.config/gcloud/configurations/config_default

test_denies_non_string_command_without_executing
FAILED because ToolExecutor raised ValueError before governance returned a denial
```

Both were made green before final verification.

## Implemented Fixes

### Command governance

- `RiskClassifier` now denies missing, empty, non-string, and unparsable commands.
- The classifier explicitly allows only MVP validation/demo shapes: pytest, ruff check, git
  status/diff, the mock demo, and the two tightly constrained Python inline forms used by timeout
  and stdout tests.
- Shell operators, wrappers (`cmd`, PowerShell, bash, sh), network tools, dependency installs,
  publish commands, aliases, and unknown commands require review or are denied.
- `ToolExecutor` performs governance before payload validation so non-string commands return
  `denied_by_governance` without reaching `subprocess.run`.

### Sensitive path fence

- Sensitive matching is case-insensitive and covers `.env`, `.env.*`, `.git-credentials`,
  `.netrc`, `.npmrc`, `.pypirc`, SSH key names, common credential filenames, secret-looking
  filenames, and common AWS/Azure/Docker/Kubernetes/GCloud/SSH paths.
- Read and write actions are denied before file content can enter `ToolResult`.

### HITL resume

- `TaskRun` has backward-compatible `pending_approval_id: str | None = None` and
  `observations: list[Feedback] = []` fields.
- Waiting runs persist the approval ID. Resume leaves pending requests waiting without creating a
  duplicate, terminates rejected/expired requests deterministically, and executes an approved
  stored action once through `execute_approved` before clearing the association and continuing.
- Tests prove one approval request and one approved execution.

### Observations and invalid actions

- Every tool result becomes a bounded persisted observation; successful read/command stdout and
  stderr are included in the next structured prompt.
- Failure observations retain redacted stdout, stderr, exit code, and timeout state in addition to
  pytest/ruff-specific fields.
- Shared redaction masks OpenAI keys and secret-looking assignments before prompt or run-state
  persistence.
- Parse, action payload, governance payload, and tool payload errors are converted to
  `invalid_action` observations, persisted for that iteration, and offered to the next iteration
  until the normal maximum is reached.

### WebUI and minor fixes

- `harness.web` exports a module-level ASGI `app` using `Path.cwd()`, preserving the documented
  `uvicorn harness.web:app` command.
- The home page reads the same JSON stores and displays run, approval, and memory counts plus the
  latest task. The adapter still exposes no tool or shell execution route.
- CLI memory listing uses public `JsonMemoryStore.list()`.
- `.test-tmp/` is ignored.
- README records that Docker daemon/Buildx were not verified in the current environment.

## Files Changed

- `.gitignore`
- `README.md`
- `src/harness/actions.py`
- `src/harness/cli.py`
- `src/harness/core/loop.py`
- `src/harness/feedback.py`
- `src/harness/governance/path_fence.py`
- `src/harness/governance/risk.py`
- `src/harness/memory.py`
- `src/harness/models.py`
- `src/harness/tools.py`
- `src/harness/web.py`
- `tests/core/test_loop.py`
- `tests/governance/test_path_fence.py`
- `tests/governance/test_risk.py`
- `tests/test_feedback.py`
- `tests/test_models.py`
- `tests/test_tools.py`
- `tests/test_web.py`
- `.superpowers/sdd/2026-08-10-coding-agent-harness/final-review-fix-report.md`

## GREEN Evidence

Focused changed-module verification:

```text
pytest -q -p no:cacheprovider tests/governance/test_risk.py \
  tests/governance/test_path_fence.py tests/test_tools.py tests/core/test_loop.py tests/test_web.py
45 passed, 1 warning in 3.35s
```

Final required verification, rerun after all hardening changes:

```text
ruff check src tests scripts
All checks passed!

pytest -q -p no:cacheprovider
96 passed, 1 warning in 4.29s

python scripts/mock_demo.py
dangerous_action=denied_by_governance
feedback_repair=completed
hitl=waiting_for_approval

git diff --check
exit 0 (only Git CRLF conversion notices)
```

## Concerns

- Docker build was optional and was not run. README accurately notes that Docker daemon and Buildx
  were not verified in this environment.
- Pytest emits one `StarletteDeprecationWarning` from FastAPI's TestClient compatibility layer;
  there are no test failures.
- Approved action consumption is persisted before execution to prevent a second resume from
  repeating the action. A process crash after that persistence and before/during external execution
  favors at-most-once behavior; the MVP JSON store does not provide transactional exactly-once
  delivery.

import json
from pathlib import Path
from typing import Annotated

import typer

from harness.config import HarnessConfig
from harness.core.loop import AgentLoop
from harness.credentials import CredentialManager
from harness.governance.approval import ApprovalStateMachine, JsonApprovalStore
from harness.llm import MockLLMClient, OpenAICompatibleClient
from harness.memory import JsonMemoryStore

app = typer.Typer()
approvals_app = typer.Typer()
credentials_app = typer.Typer()
memory_app = typer.Typer()
app.add_typer(approvals_app, name="approvals")
app.add_typer(credentials_app, name="credentials")
app.add_typer(memory_app, name="memory")

WorkspaceOption = Annotated[Path, typer.Option("--workspace")]


def _config(workspace: Path) -> HarnessConfig:
    return HarnessConfig(workspace_root=workspace)


def _print_run(run) -> None:
    typer.echo(f"{run.status.value.upper()} ({run.stop_reason})")


@app.command()
def run(
    task: str,
    workspace: WorkspaceOption,
    mock_script: Annotated[Path | None, typer.Option("--mock-script")] = None,
) -> None:
    """Run a task through the core agent loop."""
    config = _config(workspace)
    if mock_script is not None:
        script = json.loads(mock_script.read_text(encoding="utf-8"))
        llm = MockLLMClient(script)
    else:
        api_key = CredentialManager().get_api_key()
        if api_key is None:
            raise typer.BadParameter("no OpenAI API key is configured")
        llm = OpenAICompatibleClient(
            api_key=api_key,
            base_url="https://api.openai.com/v1",
            model="gpt-4o-mini",
        )
    _print_run(AgentLoop(config, llm).run(task))


@app.command()
def demo(workspace: WorkspaceOption) -> None:
    """Run a deterministic local demonstration without an API key."""
    config = _config(workspace)
    script = [{"type": "request_done", "payload": {"summary": "demo completed"}}]
    _print_run(AgentLoop(config, MockLLMClient(script)).run("run demo"))


def _approval_store(workspace: Path) -> JsonApprovalStore:
    return JsonApprovalStore(_config(workspace).paths()["approvals"])


@approvals_app.command("list")
def list_approvals(workspace: WorkspaceOption) -> None:
    """List approval requests for a workspace."""
    for request in _approval_store(workspace).list():
        typer.echo(f"{request.id} {request.status.value} {request.action.type.value}")


@approvals_app.command("approve")
def approve(
    request_id: str,
    workspace: WorkspaceOption,
) -> None:
    """Approve a pending request."""
    request = ApprovalStateMachine(_approval_store(workspace)).approve(request_id)
    typer.echo(f"{request.id} {request.status.value}")


@approvals_app.command("reject")
def reject(
    request_id: str,
    workspace: WorkspaceOption,
) -> None:
    """Reject a pending request."""
    request = ApprovalStateMachine(_approval_store(workspace)).reject(request_id)
    typer.echo(f"{request.id} {request.status.value}")


@credentials_app.command("status")
def credentials_status() -> None:
    """Show credential availability without revealing secrets."""
    status = CredentialManager().status()
    preview = status.masked_preview or ""
    typer.echo(f"openai {status.source} {preview}".rstrip())


@credentials_app.command("set")
def credentials_set() -> None:
    """Store an OpenAI API key in the system keyring."""
    api_key = typer.prompt("OpenAI API key", hide_input=True)
    CredentialManager().set_api_key(api_key)
    typer.echo("Credential stored.")


@credentials_app.command("clear")
def credentials_clear() -> None:
    """Remove the stored OpenAI API key."""
    CredentialManager().clear_api_key()
    typer.echo("Credential cleared.")


@memory_app.command("list")
def list_memory(workspace: WorkspaceOption) -> None:
    """List locally stored memory entries."""
    store = JsonMemoryStore(_config(workspace).paths()["memory"])
    for entry in store._load():
        typer.echo(f"{entry.id} {entry.kind.value} {entry.text}")

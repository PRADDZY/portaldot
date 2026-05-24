from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from portalsentinel.bootstrap import build_service
from portalsentinel.config import get_settings
from portalsentinel.models import (
    AddMemberInput,
    ApproveActionInput,
    CreateActionInput,
    CreateWorkspaceInput,
    ExecuteActionInput,
    IssueCredentialInput,
    PlanRequest,
    RevokeCredentialInput,
    SimulateRequest,
    SubmitRequest,
)

app = typer.Typer(help="PortalSentinel CLI")
console = Console()


def _service():
    return build_service(get_settings())


def _print_json(data: Any) -> None:
    console.print_json(data=json.dumps(data))


def _load_plan(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise typer.BadParameter(f"plan file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


@app.command("health")
def health() -> None:
    _print_json(_service().health())


workspace_app = typer.Typer(help="Workspace commands")
member_app = typer.Typer(help="Member commands")
credential_app = typer.Typer(help="Credential commands")
action_app = typer.Typer(help="Action commands")
agent_app = typer.Typer(help="Agent commands")
replay_app = typer.Typer(help="Replay commands")

app.add_typer(workspace_app, name="workspace")
app.add_typer(member_app, name="member")
app.add_typer(credential_app, name="credential")
app.add_typer(action_app, name="action")
app.add_typer(agent_app, name="agent")
app.add_typer(replay_app, name="replay")


@workspace_app.command("list")
def workspace_list() -> None:
    items = _service().list_workspaces()
    table = Table(title="Workspaces")
    table.add_column("ID")
    table.add_column("Name")
    table.add_column("Owner")
    table.add_column("Created At")
    for row in items:
        table.add_row(str(row["workspace_id"]), row["name"], row["owner"], row["created_at"])
    console.print(table)


@workspace_app.command("create")
def workspace_create(
    name: str = typer.Option(..., help="Workspace name"),
    metadata_hash: str = typer.Option(..., help="Metadata hash"),
    caller: str = typer.Option("demo-caller", help="Caller account"),
) -> None:
    payload = CreateWorkspaceInput(name=name, metadata_hash=metadata_hash)
    _print_json(_service().create_workspace(payload, caller=caller))


@member_app.command("add")
def member_add(
    workspace_id: int = typer.Option(..., min=1),
    account: str = typer.Option(...),
    role: str = typer.Option(..., help="owner|admin|contributor|viewer"),
    caller: str = typer.Option("demo-caller"),
) -> None:
    payload = AddMemberInput(workspace_id=workspace_id, account=account, role=role)
    _print_json(_service().add_member(payload, caller=caller))


@credential_app.command("issue")
def credential_issue(
    workspace_id: int = typer.Option(..., min=1),
    account: str = typer.Option(...),
    credential_type: str = typer.Option(...),
    credential_hash: str = typer.Option(...),
    caller: str = typer.Option("demo-caller"),
) -> None:
    payload = IssueCredentialInput(
        workspace_id=workspace_id,
        account=account,
        credential_type=credential_type,
        credential_hash=credential_hash,
    )
    _print_json(_service().issue_credential(payload, caller=caller))


@credential_app.command("revoke")
def credential_revoke(
    credential_id: int = typer.Option(..., min=1),
    caller: str = typer.Option("demo-caller"),
) -> None:
    payload = RevokeCredentialInput(credential_id=credential_id)
    _print_json(_service().revoke_credential(payload, caller=caller))


@action_app.command("create")
def action_create(
    workspace_id: int = typer.Option(..., min=1),
    action_type: str = typer.Option(...),
    payload_hash: str = typer.Option(...),
    required_role: str = typer.Option("admin"),
    min_approvals: int = typer.Option(1, min=1, max=10),
    caller: str = typer.Option("demo-caller"),
) -> None:
    payload = CreateActionInput(
        workspace_id=workspace_id,
        action_type=action_type,
        payload_hash=payload_hash,
        required_role=required_role,
        min_approvals=min_approvals,
    )
    _print_json(_service().create_action(payload, caller=caller))


@action_app.command("approve")
def action_approve(
    action_id: int = typer.Option(..., min=1),
    caller: str = typer.Option("demo-caller"),
) -> None:
    payload = ApproveActionInput(action_id=action_id)
    _print_json(_service().approve_action(payload, caller=caller))


@action_app.command("execute")
def action_execute(
    action_id: int = typer.Option(..., min=1),
    caller: str = typer.Option("demo-caller"),
) -> None:
    payload = ExecuteActionInput(action_id=action_id)
    _print_json(_service().execute_action(payload, caller=caller))


@agent_app.command("plan")
def agent_plan(
    intent: str = typer.Option(..., help="User intent"),
    workspace_id: int | None = typer.Option(None, min=1),
    out: Path | None = typer.Option(None, help="Optional output file to save plan"),
    dry_run: bool = typer.Option(True),
) -> None:
    response = _service().plan(PlanRequest(intent=intent, workspace_id=workspace_id, dry_run=dry_run))
    _print_json(response)
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(response["plan"], indent=2), encoding="utf-8")
        console.print(f"[green]Plan written to {out}[/green]")


@agent_app.command("simulate")
def agent_simulate(plan_file: Path = typer.Option(..., exists=True, file_okay=True)) -> None:
    plan = _load_plan(plan_file)
    response = _service().simulate(SimulateRequest(plan=plan))
    _print_json(response)
    if not response["ok"]:
        raise typer.Exit(code=2)


@agent_app.command("submit")
def agent_submit(
    plan_file: Path = typer.Option(..., exists=True, file_okay=True),
    caller: str = typer.Option("demo-caller"),
    confirm: bool = typer.Option(False, help="Must be true to execute"),
) -> None:
    plan = _load_plan(plan_file)
    response = _service().submit(SubmitRequest(plan=plan, caller=caller, confirm=confirm))
    _print_json(response)
    if not response["ok"]:
        raise typer.Exit(code=3)


@replay_app.command("session")
def replay_session(
    id: str = typer.Option(..., help="Session ID"),
    limit: int = typer.Option(200, min=1, max=1000),
) -> None:
    events = _service().store.list_events(session_id=id, limit=limit)
    _print_json({"session_id": id, "events": [event.model_dump() for event in events]})

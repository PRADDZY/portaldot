from __future__ import annotations

from portalsentinel.bootstrap import build_service
from portalsentinel.config import Settings
from portalsentinel.models import (
    AddMemberInput,
    ApproveActionInput,
    CreateActionInput,
    CreateWorkspaceInput,
    ExecuteActionInput,
    PlanRequest,
    SimulateRequest,
    SubmitRequest,
)


def _service(tmp_path):
    settings = Settings(
        chain_mode="mock",
        data_dir=tmp_path,
        storage_path=tmp_path / "events.db",
    )
    return build_service(settings)


def test_manual_workflow_lifecycle(tmp_path):
    service = _service(tmp_path)

    workspace = service.create_workspace(
        payload=CreateWorkspaceInput(name="Team A", metadata_hash="ipfs://workspace"),
        caller="alice",
    )
    workspace_id = workspace["workspace"]["workspace_id"]

    service.add_member(
        payload=AddMemberInput(
            workspace_id=workspace_id,
            account="bob111111111111111111111111111111111",
            role="admin",
        ),
        caller="alice",
    )
    action = service.create_action(
        payload=CreateActionInput(
            workspace_id=workspace_id,
            action_type="grant_payout",
            payload_hash="ipfs://action",
            required_role="admin",
            min_approvals=1,
        ),
        caller="alice",
    )
    action_id = action["action"]["action_id"]
    service.approve_action(payload=ApproveActionInput(action_id=action_id), caller="alice")
    executed = service.execute_action(payload=ExecuteActionInput(action_id=action_id), caller="alice")
    assert executed["action"]["status"] == "executed"


def test_plan_simulate_submit(tmp_path):
    service = _service(tmp_path)
    planned = service.plan(PlanRequest(intent="Create a team flow with identity credential and execute a grant", dry_run=True))

    plan_obj = planned["plan"]
    simulation = service.simulate(SimulateRequest(plan=plan_obj))
    assert simulation["ok"] is True

    submitted = service.submit(SubmitRequest(plan=plan_obj, confirm=True, caller="demo-caller"))
    assert submitted["ok"] is True
    assert len(submitted["steps"]) >= 3


def test_execute_requires_approvals(tmp_path):
    service = _service(tmp_path)
    workspace = service.create_workspace(
        payload=CreateWorkspaceInput(name="Team B", metadata_hash="ipfs://workspace-b"),
        caller="alice",
    )
    workspace_id = workspace["workspace"]["workspace_id"]
    action = service.create_action(
        payload=CreateActionInput(
            workspace_id=workspace_id,
            action_type="grant_payout",
            payload_hash="ipfs://grant-b",
            required_role="admin",
            min_approvals=2,
        ),
        caller="alice",
    )
    action_id = action["action"]["action_id"]
    try:
        service.execute_action(payload=ExecuteActionInput(action_id=action_id), caller="alice")
        assert False, "expected execute_action to fail without enough approvals"
    except Exception as exc:
        assert "requires 2" in str(exc) or "InsufficientApprovals" in str(exc)

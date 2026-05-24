from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from portalsentinel.bootstrap import build_service  # noqa: E402
from portalsentinel.config import Settings  # noqa: E402
from portalsentinel.models import (  # noqa: E402
    AddMemberInput,
    ApproveActionInput,
    CreateActionInput,
    CreateWorkspaceInput,
    ExecuteActionInput,
    IssueCredentialInput,
)


ALICE = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
BOB = "5FHneW46xGXgs5mUiveU4sbTyGBzmstq6Y4vdQ2sM6mYj4aS"


def run(output_path: Path, caller: str | None) -> int:
    settings = Settings()
    service = build_service(settings)
    caller = caller or ALICE

    steps: list[dict] = []
    try:
        create_workspace = service.create_workspace(
            CreateWorkspaceInput(name="PortalSentinel Demo", metadata_hash="ipfs://portalsentinel-demo-workspace"),
            caller=caller,
        )
        workspace_id = create_workspace["workspace"]["workspace_id"]
        steps.append({"step": "create_workspace", "data": create_workspace})

        add_member = service.add_member(
            AddMemberInput(workspace_id=workspace_id, account=BOB, role="admin"),
            caller=caller,
        )
        steps.append({"step": "add_member", "data": add_member})

        issue_credential = service.issue_credential(
            IssueCredentialInput(
                workspace_id=workspace_id,
                account=BOB,
                credential_type="reviewer_badge",
                credential_hash="ipfs://portalsentinel-credential",
            ),
            caller=caller,
        )
        steps.append({"step": "issue_credential", "data": issue_credential})

        create_action = service.create_action(
            CreateActionInput(
                workspace_id=workspace_id,
                action_type="grant_release",
                payload_hash="ipfs://portalsentinel-action",
                required_role="admin",
                min_approvals=1,
            ),
            caller=caller,
        )
        action_id = create_action["action"]["action_id"]
        steps.append({"step": "create_action", "data": create_action})

        approve_action = service.approve_action(payload=ApproveActionInput(action_id=action_id), caller=caller)
        steps.append({"step": "approve_action", "data": approve_action})

        execute_action = service.execute_action(payload=ExecuteActionInput(action_id=action_id), caller=caller)
        steps.append({"step": "execute_action", "data": execute_action})

        list_workspaces = service.list_workspaces()
        list_members = service.list_members(workspace_id)
        list_actions = service.list_actions(workspace_id)

        evidence = {
            "ok": True,
            "mode": settings.chain_mode,
            "workspace_id": workspace_id,
            "action_id": action_id,
            "caller": caller,
            "steps": steps,
            "list_views": {
                "workspaces": list_workspaces,
                "members": list_members,
                "actions": list_actions,
            },
            "events_tail": [row.model_dump() for row in service.store.list_events(limit=50)],
        }
    except Exception as exc:
        evidence = {"ok": False, "mode": settings.chain_mode, "error": str(exc), "steps": steps}

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(f"Wrote evidence to {output_path}")
    return 0 if evidence.get("ok") else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Run full PortalSentinel workflow and capture evidence")
    parser.add_argument(
        "--output",
        default=str(ROOT / "docs" / "submission" / "evidence-latest.json"),
        help="Output evidence JSON path",
    )
    parser.add_argument("--caller", default=None, help="Override caller account")
    args = parser.parse_args()
    return run(Path(args.output), caller=args.caller)


if __name__ == "__main__":
    raise SystemExit(main())

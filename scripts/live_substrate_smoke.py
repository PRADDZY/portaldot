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


def ensure_live_settings(settings: Settings) -> None:
    if settings.chain_mode != "substrate":
        raise RuntimeError("live substrate smoke requires CHAIN_MODE=substrate")
    if not settings.contract_address:
        raise RuntimeError("CONTRACT_ADDRESS is required for live substrate smoke")
    if not settings.contract_metadata_path:
        raise RuntimeError("CONTRACT_METADATA_PATH is required for live substrate smoke")
    metadata_path = Path(settings.contract_metadata_path)
    if not metadata_path.is_absolute():
        metadata_path = ROOT / metadata_path
    if not metadata_path.exists():
        raise RuntimeError(f"contract metadata file not found: {metadata_path}")
    if not settings.portaldot_ws:
        raise RuntimeError("PORTALDOT_WS is required for live substrate smoke")
    if not settings.signer_uri:
        raise RuntimeError("DEMO_SIGNER_URI is required for live substrate smoke")


def run(output_path: Path, caller: str | None) -> int:
    settings = Settings()
    caller = caller or ALICE

    result: dict[str, object] = {
        "ok": False,
        "mode": settings.chain_mode,
        "caller": caller,
        "contract_address": settings.contract_address,
        "portaldot_ws": settings.portaldot_ws,
    }

    try:
        ensure_live_settings(settings)
        service = build_service(settings)
        health = service.health()
        result["health"] = health

        steps: list[dict[str, object]] = []

        create_workspace = service.create_workspace(
            CreateWorkspaceInput(name="PortalSentinel Live Workspace", metadata_hash="ipfs://portalsentinel-live"),
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
                credential_type="live_reviewer_badge",
                credential_hash="ipfs://portalsentinel-live-credential",
            ),
            caller=caller,
        )
        steps.append({"step": "issue_credential", "data": issue_credential})

        create_action = service.create_action(
            CreateActionInput(
                workspace_id=workspace_id,
                action_type="live_release",
                payload_hash="ipfs://portalsentinel-live-action",
                required_role="admin",
                min_approvals=1,
            ),
            caller=caller,
        )
        success_action_id = create_action["action"]["action_id"]
        steps.append({"step": "create_action", "data": create_action})

        approve_action = service.approve_action(ApproveActionInput(action_id=success_action_id), caller=caller)
        steps.append({"step": "approve_action", "data": approve_action})

        execute_action = service.execute_action(ExecuteActionInput(action_id=success_action_id), caller=caller)
        steps.append({"step": "execute_action", "data": execute_action})

        failure_action = service.create_action(
            CreateActionInput(
                workspace_id=workspace_id,
                action_type="live_failure_path",
                payload_hash="ipfs://portalsentinel-live-failure",
                required_role="admin",
                min_approvals=2,
            ),
            caller=caller,
        )
        failure_action_id = failure_action["action"]["action_id"]
        failure_result: dict[str, object] = {
            "action_id": failure_action_id,
            "ok": False,
        }
        try:
            service.execute_action(ExecuteActionInput(action_id=failure_action_id), caller=caller)
            failure_result["error"] = "expected insufficient approval failure but execution succeeded"
        except Exception as exc:
            failure_result["ok"] = True
            failure_result["expected_error"] = str(exc)

        result["success_flow"] = {
            "workspace_id": workspace_id,
            "action_id": success_action_id,
            "steps": steps,
        }
        result["failure_flow"] = failure_result
        result["list_views"] = {
            "workspaces": service.list_workspaces(),
            "members": service.list_members(workspace_id),
            "actions": service.list_actions(workspace_id),
        }
        result["events_tail"] = [row.model_dump() for row in service.store.list_events(limit=50)]
        result["ok"] = bool(failure_result.get("ok"))
    except Exception as exc:
        result["error"] = str(exc)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Wrote live substrate smoke report to {output_path}")
    return 0 if result.get("ok") else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Run live substrate smoke workflow")
    parser.add_argument(
        "--output",
        default=str(ROOT / "data" / "live-substrate-smoke.json"),
        help="Output report path",
    )
    parser.add_argument("--caller", default=None, help="Override caller account")
    args = parser.parse_args()
    return run(Path(args.output), caller=args.caller)


if __name__ == "__main__":
    raise SystemExit(main())

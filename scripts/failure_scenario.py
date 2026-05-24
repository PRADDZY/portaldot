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
    CreateActionInput,
    CreateWorkspaceInput,
    ExecuteActionInput,
)


ALICE = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"


def run(output_path: Path, caller: str | None) -> int:
    settings = Settings()
    service = build_service(settings)
    caller = caller or ALICE

    result: dict = {
        "ok": False,
        "mode": settings.chain_mode,
        "scenario": "execute before required approvals",
    }
    try:
        workspace = service.create_workspace(
            CreateWorkspaceInput(name="Failure Demo Workspace", metadata_hash="ipfs://failure-demo"),
            caller=caller,
        )
        workspace_id = workspace["workspace"]["workspace_id"]
        action = service.create_action(
            CreateActionInput(
                workspace_id=workspace_id,
                action_type="release_payment",
                payload_hash="ipfs://failure-action",
                required_role="admin",
                min_approvals=2,
            ),
            caller=caller,
        )
        action_id = action["action"]["action_id"]
        try:
            service.execute_action(ExecuteActionInput(action_id=action_id), caller=caller)
            result["error"] = "expected failure but execution succeeded"
        except Exception as exc:
            result["ok"] = True
            result["expected_error"] = str(exc)
            result["workspace_id"] = workspace_id
            result["action_id"] = action_id
    except Exception as exc:
        result["fatal_error"] = str(exc)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Wrote failure scenario to {output_path}")
    return 0 if result.get("ok") else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate deterministic failure scenario evidence")
    parser.add_argument(
        "--output",
        default=str(ROOT / "docs" / "submission" / "failure-scenario.json"),
        help="Output path for failure scenario evidence",
    )
    parser.add_argument("--caller", default=None, help="Override caller account")
    args = parser.parse_args()
    return run(Path(args.output), caller=args.caller)


if __name__ == "__main__":
    raise SystemExit(main())

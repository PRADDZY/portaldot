from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from portalsentinel.adapters.base import ChainAdapter
from portalsentinel.ai import AIPlanner
from portalsentinel.models import (
    ActionPlan,
    AddMemberInput,
    ApproveActionInput,
    CreateActionInput,
    CreateWorkspaceInput,
    ExecuteActionInput,
    IssueCredentialInput,
    PlanRequest,
    RevokeCredentialInput,
    Role,
    SimulateRequest,
    SubmitRequest,
)
from portalsentinel.store import EventStore


@dataclass
class PortalService:
    adapter: ChainAdapter
    store: EventStore
    planner: AIPlanner
    mode: str

    def health(self) -> dict[str, Any]:
        chain = self.adapter.health()
        return {
            "ok": True,
            "mode": self.mode,
            "chain": chain.model_dump(),
        }

    def list_workspaces(self) -> list[dict[str, Any]]:
        return [w.model_dump() for w in self.adapter.list_workspaces()]

    def list_members(self, workspace_id: int) -> list[dict[str, Any]]:
        return [m.model_dump() for m in self.adapter.list_members(workspace_id)]

    def list_actions(self, workspace_id: int | None = None) -> list[dict[str, Any]]:
        return [a.model_dump() for a in self.adapter.list_actions(workspace_id)]

    def create_workspace(self, payload: CreateWorkspaceInput, caller: str) -> dict[str, Any]:
        workspace, receipt = self.adapter.create_workspace(payload, caller=caller)
        self.store.log_event(
            source="chain",
            event_type="workspace.created",
            payload={"workspace": workspace.model_dump(), "receipt": receipt.model_dump()},
        )
        return {"workspace": workspace.model_dump(), "receipt": receipt.model_dump()}

    def add_member(self, payload: AddMemberInput, caller: str) -> dict[str, Any]:
        member, receipt = self.adapter.add_member(payload, caller=caller)
        self.store.log_event(
            source="chain",
            event_type="member.added",
            payload={"member": member.model_dump(), "receipt": receipt.model_dump()},
        )
        return {"member": member.model_dump(), "receipt": receipt.model_dump()}

    def issue_credential(self, payload: IssueCredentialInput, caller: str) -> dict[str, Any]:
        credential, receipt = self.adapter.issue_credential(payload, caller=caller)
        self.store.log_event(
            source="chain",
            event_type="credential.issued",
            payload={"credential": credential.model_dump(), "receipt": receipt.model_dump()},
        )
        return {"credential": credential.model_dump(), "receipt": receipt.model_dump()}

    def create_action(self, payload: CreateActionInput, caller: str) -> dict[str, Any]:
        action, receipt = self.adapter.create_action(payload, caller=caller)
        self.store.log_event(
            source="chain",
            event_type="action.created",
            payload={"action": action.model_dump(), "receipt": receipt.model_dump()},
        )
        return {"action": action.model_dump(), "receipt": receipt.model_dump()}

    def approve_action(self, payload: ApproveActionInput, caller: str) -> dict[str, Any]:
        action, receipt = self.adapter.approve_action(payload, caller=caller)
        self.store.log_event(
            source="chain",
            event_type="action.approved",
            payload={"action": action.model_dump(), "receipt": receipt.model_dump()},
        )
        return {"action": action.model_dump(), "receipt": receipt.model_dump()}

    def execute_action(self, payload: ExecuteActionInput, caller: str) -> dict[str, Any]:
        action, receipt = self.adapter.execute_action(payload, caller=caller)
        self.store.log_event(
            source="chain",
            event_type="action.executed",
            payload={"action": action.model_dump(), "receipt": receipt.model_dump()},
        )
        return {"action": action.model_dump(), "receipt": receipt.model_dump()}

    def revoke_credential(self, payload: RevokeCredentialInput, caller: str) -> dict[str, Any]:
        credential, receipt = self.adapter.revoke_credential(payload, caller=caller)
        self.store.log_event(
            source="chain",
            event_type="credential.revoked",
            payload={"credential": credential.model_dump(), "receipt": receipt.model_dump()},
        )
        return {"credential": credential.model_dump(), "receipt": receipt.model_dump()}

    def plan(self, request: PlanRequest) -> dict[str, Any]:
        plan = self.planner.build_plan(request)
        session_id = self.store.create_session(mode=self.mode, intent=request.intent, status="planned", plan=plan)
        self.store.log_event(
            session_id=session_id,
            source="agent",
            event_type="plan.created",
            payload={"plan": plan.model_dump(), "dry_run": request.dry_run},
        )
        return {"session_id": session_id, "plan": plan.model_dump()}

    def simulate(self, request: SimulateRequest) -> dict[str, Any]:
        checks: list[dict[str, Any]] = []
        state: dict[str, Any] = {"workspace_id": request.plan.workspace_id}
        synthetic_workspace_id = state.get("workspace_id") or 1
        synthetic_action_id = 1
        for idx, step in enumerate(request.plan.steps, start=1):
            ok = True
            reason = "valid"
            try:
                self._validate_step(step.action, step.params, state)
                if step.action == "create_workspace":
                    state["workspace_id"] = int(step.params.get("workspace_id") or synthetic_workspace_id)
                    synthetic_workspace_id += 1
                elif step.action == "create_action":
                    state["action_id"] = int(step.params.get("action_id") or synthetic_action_id)
                    synthetic_action_id += 1
            except Exception as exc:
                ok = False
                reason = str(exc)
            checks.append({"step": idx, "action": step.action, "ok": ok, "reason": reason, "params": step.params})
        passed = all(check["ok"] for check in checks)
        return {"ok": passed, "checks": checks}

    def submit(self, request: SubmitRequest) -> dict[str, Any]:
        if not request.confirm:
            raise ValueError("submit requires confirm=true")

        session_id = self.store.create_session(mode=self.mode, intent=request.plan.intent, status="running", plan=request.plan)
        self.store.log_event(
            session_id=session_id,
            source="agent",
            event_type="submit.started",
            payload={"plan_id": request.plan.plan_id},
        )

        state: dict[str, Any] = {"workspace_id": request.plan.workspace_id, "action_id": None}
        results: list[dict[str, Any]] = []

        try:
            for step in request.plan.steps:
                result = self._execute_step(step.action, dict(step.params), state, caller=request.caller)
                results.append({"action": step.action, "result": result})
                self.store.log_event(
                    session_id=session_id,
                    source="agent",
                    event_type=f"submit.step.{step.action}",
                    payload=result,
                )
            self.store.update_session(session_id, status="completed")
            self.store.log_event(
                session_id=session_id,
                source="agent",
                event_type="submit.completed",
                payload={"steps": len(results)},
            )
            return {"session_id": session_id, "ok": True, "steps": results}
        except Exception as exc:
            self.store.update_session(session_id, status="failed")
            self.store.log_event(
                session_id=session_id,
                source="agent",
                event_type="submit.failed",
                payload={"error": str(exc), "steps": len(results)},
            )
            return {"session_id": session_id, "ok": False, "error": str(exc), "steps": results}

    def _resolve_workspace_id(self, params: dict[str, Any], state: dict[str, Any]) -> int:
        workspace_id = params.get("workspace_id") or state.get("workspace_id")
        if not workspace_id:
            raise ValueError("workspace_id is required for this action")
        return int(workspace_id)

    def _resolve_action_id(self, params: dict[str, Any], state: dict[str, Any]) -> int:
        action_id = params.get("action_id") or state.get("action_id")
        if not action_id:
            raise ValueError("action_id is required for this action")
        return int(action_id)

    def _validate_step(self, action: str, params: dict[str, Any], state: dict[str, Any]) -> None:
        if action == "create_workspace":
            CreateWorkspaceInput.model_validate(params)
            return
        if action == "add_member":
            params["workspace_id"] = self._resolve_workspace_id(params, state)
            AddMemberInput.model_validate(params)
            return
        if action == "issue_credential":
            params["workspace_id"] = self._resolve_workspace_id(params, state)
            IssueCredentialInput.model_validate(params)
            return
        if action == "create_action":
            params["workspace_id"] = self._resolve_workspace_id(params, state)
            if "required_role" not in params:
                params["required_role"] = Role.ADMIN.value
            CreateActionInput.model_validate(params)
            return
        if action == "approve_action":
            params["action_id"] = self._resolve_action_id(params, state)
            ApproveActionInput.model_validate(params)
            return
        if action == "execute_action":
            params["action_id"] = self._resolve_action_id(params, state)
            ExecuteActionInput.model_validate(params)
            return
        if action == "revoke_credential":
            RevokeCredentialInput.model_validate(params)
            return
        raise ValueError(f"unsupported action type: {action}")

    def _execute_step(self, action: str, params: dict[str, Any], state: dict[str, Any], caller: str) -> dict[str, Any]:
        if action == "create_workspace":
            payload = CreateWorkspaceInput.model_validate(params)
            out = self.create_workspace(payload, caller=caller)
            state["workspace_id"] = out["workspace"]["workspace_id"]
            return out
        if action == "add_member":
            params["workspace_id"] = self._resolve_workspace_id(params, state)
            payload = AddMemberInput.model_validate(params)
            return self.add_member(payload, caller=caller)
        if action == "issue_credential":
            params["workspace_id"] = self._resolve_workspace_id(params, state)
            payload = IssueCredentialInput.model_validate(params)
            return self.issue_credential(payload, caller=caller)
        if action == "create_action":
            params["workspace_id"] = self._resolve_workspace_id(params, state)
            params.setdefault("required_role", Role.ADMIN.value)
            payload = CreateActionInput.model_validate(params)
            out = self.create_action(payload, caller=caller)
            state["action_id"] = out["action"]["action_id"]
            return out
        if action == "approve_action":
            params["action_id"] = self._resolve_action_id(params, state)
            payload = ApproveActionInput.model_validate(params)
            return self.approve_action(payload, caller=caller)
        if action == "execute_action":
            params["action_id"] = self._resolve_action_id(params, state)
            payload = ExecuteActionInput.model_validate(params)
            return self.execute_action(payload, caller=caller)
        if action == "revoke_credential":
            payload = RevokeCredentialInput.model_validate(params)
            return self.revoke_credential(payload, caller=caller)
        raise ValueError(f"unsupported action type: {action}")

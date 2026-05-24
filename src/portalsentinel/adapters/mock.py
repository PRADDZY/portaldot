from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from portalsentinel.adapters.base import ChainAdapter
from portalsentinel.models import (
    ActionRecord,
    ActionStatus,
    AddMemberInput,
    ApproveActionInput,
    ChainHealth,
    ChainTxReceipt,
    CreateActionInput,
    CreateWorkspaceInput,
    CredentialRecord,
    ExecuteActionInput,
    IssueCredentialInput,
    MemberRecord,
    RevokeCredentialInput,
    Role,
    WorkspaceRecord,
    utc_now_iso,
)


class MockChainAdapter(ChainAdapter):
    """Deterministic in-memory adapter used for local build and tests."""

    def __init__(self, state_path: Path | None = None) -> None:
        self._state_path = state_path
        self._workspace_id = 0
        self._credential_id = 0
        self._action_id = 0
        self._workspaces: dict[int, WorkspaceRecord] = {}
        self._members: dict[int, dict[str, MemberRecord]] = defaultdict(dict)
        self._credentials: dict[int, CredentialRecord] = {}
        self._actions: dict[int, ActionRecord] = {}
        self._workspace_actions: dict[int, list[int]] = defaultdict(list)
        self._approvals: dict[int, set[str]] = defaultdict(set)
        self._load_state()

    def _tx(self, label: str, payload: dict[str, Any]) -> ChainTxReceipt:
        body = f"{label}:{payload}:{utc_now_iso()}".encode("utf-8")
        digest = hashlib.sha256(body).hexdigest()
        tx_hash = f"0x{digest}"
        block_hash = f"0x{digest[::-1]}"
        return ChainTxReceipt(
            tx_hash=tx_hash,
            block_hash=block_hash,
            success=True,
            message=f"mock {label} accepted",
            events=[{"label": label, "payload": payload}],
        )

    def _load_state(self) -> None:
        if not self._state_path or not self._state_path.exists():
            return
        raw = json.loads(self._state_path.read_text(encoding="utf-8"))
        self._workspace_id = int(raw.get("workspace_id", 0))
        self._credential_id = int(raw.get("credential_id", 0))
        self._action_id = int(raw.get("action_id", 0))

        for row in raw.get("workspaces", []):
            workspace = WorkspaceRecord.model_validate(row)
            self._workspaces[workspace.workspace_id] = workspace

        for row in raw.get("members", []):
            member = MemberRecord.model_validate(row)
            self._members[member.workspace_id][member.account] = member

        for row in raw.get("credentials", []):
            credential = CredentialRecord.model_validate(row)
            self._credentials[credential.credential_id] = credential

        for row in raw.get("actions", []):
            action = ActionRecord.model_validate(row)
            self._actions[action.action_id] = action
            self._workspace_actions[action.workspace_id].append(action.action_id)

        for action_id, accounts in raw.get("approvals", {}).items():
            self._approvals[int(action_id)] = set(accounts)

    def _save_state(self) -> None:
        if not self._state_path:
            return
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "workspace_id": self._workspace_id,
            "credential_id": self._credential_id,
            "action_id": self._action_id,
            "workspaces": [row.model_dump() for row in self._workspaces.values()],
            "members": [row.model_dump() for ws in self._members.values() for row in ws.values()],
            "credentials": [row.model_dump() for row in self._credentials.values()],
            "actions": [row.model_dump() for row in self._actions.values()],
            "approvals": {str(action_id): sorted(list(accounts)) for action_id, accounts in self._approvals.items()},
        }
        self._state_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _role_rank(self, role: Role) -> int:
        order = {
            Role.OWNER: 4,
            Role.ADMIN: 3,
            Role.CONTRIBUTOR: 2,
            Role.VIEWER: 1,
        }
        return order[role]

    def _member_role(self, workspace_id: int, caller: str) -> Role | None:
        member = self._members.get(workspace_id, {}).get(caller)
        return member.role if member else None

    def _assert_workspace_exists(self, workspace_id: int) -> WorkspaceRecord:
        workspace = self._workspaces.get(workspace_id)
        if workspace is None:
            raise ValueError(f"workspace {workspace_id} does not exist")
        return workspace

    def _assert_role(self, workspace_id: int, caller: str, minimum: Role) -> None:
        role = self._member_role(workspace_id, caller)
        if role is None:
            raise PermissionError(f"caller {caller} is not a workspace member")
        if self._role_rank(role) < self._role_rank(minimum):
            raise PermissionError(f"caller {caller} does not have required role {minimum.value}")

    def health(self) -> ChainHealth:
        return ChainHealth(mode="mock", connected=True, node="mock://local", details={"backend": "in-memory"})

    def list_workspaces(self) -> list[WorkspaceRecord]:
        return sorted(self._workspaces.values(), key=lambda x: x.workspace_id)

    def list_members(self, workspace_id: int) -> list[MemberRecord]:
        self._assert_workspace_exists(workspace_id)
        members = self._members.get(workspace_id, {})
        return sorted(members.values(), key=lambda x: x.added_at)

    def list_actions(self, workspace_id: int | None = None) -> list[ActionRecord]:
        if workspace_id is None:
            rows = list(self._actions.values())
        else:
            self._assert_workspace_exists(workspace_id)
            rows = [self._actions[action_id] for action_id in self._workspace_actions.get(workspace_id, [])]
        return sorted(rows, key=lambda x: x.action_id)

    def create_workspace(self, payload: CreateWorkspaceInput, *, caller: str) -> tuple[WorkspaceRecord, ChainTxReceipt]:
        self._workspace_id += 1
        workspace = WorkspaceRecord(
            workspace_id=self._workspace_id,
            name=payload.name,
            metadata_hash=payload.metadata_hash,
            owner=caller,
        )
        self._workspaces[workspace.workspace_id] = workspace
        self._members[workspace.workspace_id][caller] = MemberRecord(
            workspace_id=workspace.workspace_id,
            account=caller,
            role=Role.OWNER,
        )
        self._save_state()
        receipt = self._tx("create_workspace", payload.model_dump())
        return workspace, receipt

    def add_member(self, payload: AddMemberInput, *, caller: str) -> tuple[MemberRecord, ChainTxReceipt]:
        self._assert_workspace_exists(payload.workspace_id)
        self._assert_role(payload.workspace_id, caller, Role.ADMIN)
        member = MemberRecord(workspace_id=payload.workspace_id, account=payload.account, role=payload.role)
        self._members[payload.workspace_id][payload.account] = member
        self._save_state()
        receipt = self._tx("add_member", payload.model_dump())
        return member, receipt

    def issue_credential(
        self, payload: IssueCredentialInput, *, caller: str
    ) -> tuple[CredentialRecord, ChainTxReceipt]:
        self._assert_workspace_exists(payload.workspace_id)
        self._assert_role(payload.workspace_id, caller, Role.ADMIN)
        self._credential_id += 1
        record = CredentialRecord(
            credential_id=self._credential_id,
            workspace_id=payload.workspace_id,
            account=payload.account,
            credential_type=payload.credential_type,
            credential_hash=payload.credential_hash,
        )
        self._credentials[record.credential_id] = record
        self._save_state()
        receipt = self._tx("issue_credential", payload.model_dump())
        return record, receipt

    def create_action(self, payload: CreateActionInput, *, caller: str) -> tuple[ActionRecord, ChainTxReceipt]:
        self._assert_workspace_exists(payload.workspace_id)
        self._assert_role(payload.workspace_id, caller, Role.CONTRIBUTOR)
        self._action_id += 1
        action = ActionRecord(
            action_id=self._action_id,
            workspace_id=payload.workspace_id,
            action_type=payload.action_type,
            payload_hash=payload.payload_hash,
            required_role=payload.required_role,
            min_approvals=payload.min_approvals,
            approvals=0,
            status=ActionStatus.PENDING,
            proposer=caller,
        )
        self._actions[action.action_id] = action
        self._workspace_actions[payload.workspace_id].append(action.action_id)
        self._save_state()
        receipt = self._tx("create_action", payload.model_dump())
        return action, receipt

    def approve_action(self, payload: ApproveActionInput, *, caller: str) -> tuple[ActionRecord, ChainTxReceipt]:
        action = self._actions.get(payload.action_id)
        if action is None:
            raise ValueError(f"action {payload.action_id} does not exist")
        self._assert_role(action.workspace_id, caller, action.required_role)
        if action.status == ActionStatus.EXECUTED:
            raise ValueError("cannot approve an already executed action")
        if caller in self._approvals[action.action_id]:
            raise ValueError(f"caller {caller} already approved action {action.action_id}")
        self._approvals[action.action_id].add(caller)
        action.approvals = len(self._approvals[action.action_id])
        if action.approvals >= action.min_approvals:
            action.status = ActionStatus.READY
        self._save_state()
        receipt = self._tx("approve_action", payload.model_dump())
        return action, receipt

    def execute_action(self, payload: ExecuteActionInput, *, caller: str) -> tuple[ActionRecord, ChainTxReceipt]:
        action = self._actions.get(payload.action_id)
        if action is None:
            raise ValueError(f"action {payload.action_id} does not exist")
        self._assert_role(action.workspace_id, caller, action.required_role)
        if action.status == ActionStatus.EXECUTED:
            raise ValueError(f"action {action.action_id} already executed")
        if action.approvals < action.min_approvals:
            raise ValueError(
                f"action {action.action_id} has {action.approvals} approvals but requires {action.min_approvals}"
            )
        action.status = ActionStatus.EXECUTED
        action.executed_at = utc_now_iso()
        self._save_state()
        receipt = self._tx("execute_action", payload.model_dump())
        return action, receipt

    def revoke_credential(
        self, payload: RevokeCredentialInput, *, caller: str
    ) -> tuple[CredentialRecord, ChainTxReceipt]:
        record = self._credentials.get(payload.credential_id)
        if record is None:
            raise ValueError(f"credential {payload.credential_id} does not exist")
        self._assert_role(record.workspace_id, caller, Role.ADMIN)
        if record.revoked:
            raise ValueError(f"credential {record.credential_id} already revoked")
        record.revoked = True
        self._save_state()
        receipt = self._tx("revoke_credential", payload.model_dump())
        return record, receipt

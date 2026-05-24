from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
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
)

try:
    from substrateinterface import Keypair, SubstrateInterface
    from substrateinterface.contracts import ContractInstance
except Exception:  # pragma: no cover - import guard for local env without substrate deps
    Keypair = None
    SubstrateInterface = None
    ContractInstance = None


@dataclass
class SubstrateAdapterConfig:
    ws_url: str
    ss58_format: int
    signer_uri: str
    contract_address: str
    contract_metadata_path: str
    explorer_base_url: str | None = None


class SubstrateContractAdapter(ChainAdapter):
    """Adapter for Portaldot substrate mode using py-substrate-interface contract calls."""

    def __init__(self, cfg: SubstrateAdapterConfig) -> None:
        if SubstrateInterface is None or Keypair is None or ContractInstance is None:
            raise RuntimeError(
                "substrate-interface dependency is not available. Install project deps before using substrate mode."
            )

        self.cfg = cfg
        self.substrate = SubstrateInterface(url=cfg.ws_url, ss58_format=cfg.ss58_format)
        self.signer = Keypair.create_from_uri(cfg.signer_uri)
        self.contract = ContractInstance.create_from_address(
            contract_address=cfg.contract_address,
            metadata_file=cfg.contract_metadata_path,
            substrate=self.substrate,
        )

    def _explorer_url(self, tx_hash: str) -> str | None:
        if not self.cfg.explorer_base_url or not tx_hash:
            return None
        return f"{self.cfg.explorer_base_url.rstrip('/')}/extrinsic/{tx_hash}"

    def _to_iso_timestamp(self, value: Any) -> str:
        if value is None:
            return datetime.now(timezone.utc).isoformat()
        try:
            raw = int(value)
            # Contract block timestamp is usually milliseconds on Substrate.
            epoch_seconds = raw / 1000.0 if raw > 1_000_000_000_000 else float(raw)
            return datetime.fromtimestamp(epoch_seconds, tz=timezone.utc).isoformat()
        except Exception:
            return datetime.now(timezone.utc).isoformat()

    def _to_account(self, value: Any) -> str:
        if value is None:
            return ""
        if hasattr(value, "ss58_address"):
            return str(value.ss58_address)
        return str(value)

    def _to_role(self, value: Any) -> Role:
        if isinstance(value, Role):
            return value
        if isinstance(value, dict) and value:
            key = next(iter(value.keys()))
            value = key
        if isinstance(value, (int, float)):
            mapping = {0: Role.OWNER, 1: Role.ADMIN, 2: Role.CONTRIBUTOR, 3: Role.VIEWER}
            return mapping.get(int(value), Role.VIEWER)
        key = str(value).strip().lower()
        mapping = {
            "owner": Role.OWNER,
            "admin": Role.ADMIN,
            "contributor": Role.CONTRIBUTOR,
            "viewer": Role.VIEWER,
        }
        return mapping.get(key, Role.VIEWER)

    def _unwrap(self, value: Any) -> Any:
        """Normalize nested substrate contract read return values."""
        if hasattr(value, "value"):
            return self._unwrap(value.value)
        if isinstance(value, dict):
            if "Ok" in value and len(value) == 1:
                return self._unwrap(value["Ok"])
            if "ok" in value and len(value) == 1:
                return self._unwrap(value["ok"])
            if "Some" in value and len(value) == 1:
                return self._unwrap(value["Some"])
            if "None" in value and len(value) == 1:
                return None
            return {k: self._unwrap(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._unwrap(item) for item in value]
        return value

    def _read_value(self, method: str, args: dict[str, Any]) -> Any:
        result = self.contract.read(keypair=self.signer, method=method, args=args)
        if hasattr(result, "contract_result_data"):
            return self._unwrap(result.contract_result_data)
        if hasattr(result, "value"):
            return self._unwrap(result.value)
        return self._unwrap(result)

    def _receipt(self, contract_receipt: Any) -> ChainTxReceipt:
        tx_hash = str(getattr(contract_receipt, "extrinsic_hash", "") or "")
        block_hash = getattr(contract_receipt, "block_hash", None)
        success = bool(getattr(contract_receipt, "is_success", True))
        fee = getattr(contract_receipt, "total_fee_amount", None)
        events: list[dict[str, Any]] = []
        triggered = getattr(contract_receipt, "triggered_events", None) or []
        for event in triggered:
            payload = getattr(event, "value", None)
            if isinstance(payload, dict):
                events.append(payload)
            else:
                events.append({"raw": str(payload)})
        error_message = getattr(contract_receipt, "error_message", None)
        return ChainTxReceipt(
            tx_hash=tx_hash,
            block_hash=str(block_hash) if block_hash is not None else None,
            success=success,
            fee=int(fee) if isinstance(fee, (int, float)) else None,
            events=events,
            explorer_url=self._explorer_url(tx_hash),
            message=None if success else str(error_message or "execution failed"),
        )

    def _exec(self, method: str, args: dict[str, Any]) -> ChainTxReceipt:
        contract_receipt = self.contract.exec(
            keypair=self.signer,
            method=method,
            args=args,
            value=0,
            gas_limit={"ref_time": 2_000_000_000, "proof_size": 128_000},
        )
        return self._receipt(contract_receipt)

    def _parse_workspace(self, raw: dict[str, Any], workspace_id: int | None = None) -> WorkspaceRecord:
        return WorkspaceRecord(
            workspace_id=int(raw.get("workspace_id", workspace_id or 0)),
            name=str(raw.get("name", "")),
            metadata_hash=str(raw.get("metadata_hash", "")),
            owner=self._to_account(raw.get("owner")),
            created_at=self._to_iso_timestamp(raw.get("created_at")),
        )

    def _parse_action(self, raw: dict[str, Any], action_id: int | None = None) -> ActionRecord:
        approvals = int(raw.get("approvals", 0))
        min_approvals = int(raw.get("min_approvals", 1))
        executed = bool(raw.get("executed", False))
        status = ActionStatus.EXECUTED if executed else (ActionStatus.READY if approvals >= min_approvals else ActionStatus.PENDING)
        executed_at = raw.get("executed_at")
        if isinstance(executed_at, dict) and "Some" in executed_at:
            executed_at = executed_at["Some"]
        if isinstance(executed_at, dict) and "None" in executed_at:
            executed_at = None
        return ActionRecord(
            action_id=int(raw.get("action_id", action_id or 0)),
            workspace_id=int(raw.get("workspace_id", 0)),
            action_type=str(raw.get("action_type", "")),
            payload_hash=str(raw.get("payload_hash", "")),
            required_role=self._to_role(raw.get("required_role")),
            min_approvals=min_approvals,
            approvals=approvals,
            proposer=self._to_account(raw.get("proposer")),
            status=status,
            created_at=self._to_iso_timestamp(raw.get("created_at")),
            executed_at=self._to_iso_timestamp(executed_at) if executed_at is not None else None,
        )

    def _read_workspace(self, workspace_id: int) -> WorkspaceRecord:
        raw = self._read_value("get_workspace", {"workspace_id": workspace_id})
        if raw is None:
            raise ValueError(f"workspace {workspace_id} not found")
        return self._parse_workspace(raw, workspace_id=workspace_id)

    def _read_member_role(self, workspace_id: int, account: str) -> Role:
        raw = self._read_value("get_member_role", {"workspace_id": workspace_id, "account": account})
        if raw is None:
            raise ValueError(f"member {account} not found for workspace {workspace_id}")
        return self._to_role(raw)

    def _read_action(self, action_id: int) -> ActionRecord:
        raw = self._read_value("get_action", {"action_id": action_id})
        if raw is None:
            raise ValueError(f"action {action_id} not found")
        return self._parse_action(raw, action_id=action_id)

    def _read_credential(self, credential_id: int) -> CredentialRecord:
        raw = self._read_value("get_credential", {"credential_id": credential_id})
        if raw is None:
            raise ValueError(f"credential {credential_id} not found")
        return CredentialRecord(
            credential_id=int(raw.get("credential_id", credential_id)),
            workspace_id=int(raw.get("workspace_id", 0)),
            account=self._to_account(raw.get("account")),
            credential_type=str(raw.get("credential_type", "")),
            credential_hash=str(raw.get("credential_hash", "")),
            revoked=bool(raw.get("revoked", False)),
            created_at=self._to_iso_timestamp(raw.get("issued_at")),
        )

    def health(self) -> ChainHealth:
        chain_name = str(self.substrate.rpc_request("system_chain", [])["result"])
        node_name = str(self.substrate.rpc_request("system_name", [])["result"])
        return ChainHealth(
            mode="substrate",
            connected=True,
            node=self.cfg.ws_url,
            details={"chain": chain_name, "node": node_name, "contract": self.cfg.contract_address},
        )

    def list_workspaces(self) -> list[WorkspaceRecord]:
        count = int(self._read_value("workspace_count", {}))
        rows: list[WorkspaceRecord] = []
        for idx in range(1, count + 1):
            workspace_id = self._read_value("workspace_id_at", {"index": idx})
            if workspace_id is None:
                continue
            rows.append(self._read_workspace(int(workspace_id)))
        return rows

    def list_members(self, workspace_id: int) -> list[MemberRecord]:
        count = int(self._read_value("member_count", {"workspace_id": workspace_id}))
        rows: list[MemberRecord] = []
        for idx in range(1, count + 1):
            account = self._read_value("member_at", {"workspace_id": workspace_id, "index": idx})
            if account is None:
                continue
            account_str = self._to_account(account)
            role = self._read_member_role(workspace_id, account_str)
            rows.append(MemberRecord(workspace_id=workspace_id, account=account_str, role=role))
        return rows

    def list_actions(self, workspace_id: int | None = None) -> list[ActionRecord]:
        rows: list[ActionRecord] = []
        if workspace_id is None:
            count = int(self._read_value("action_count", {}))
            for idx in range(1, count + 1):
                action_id = self._read_value("action_id_at", {"index": idx})
                if action_id is None:
                    continue
                rows.append(self._read_action(int(action_id)))
            return rows

        count = int(self._read_value("workspace_action_count", {"workspace_id": workspace_id}))
        for idx in range(1, count + 1):
            action_id = self._read_value("workspace_action_id_at", {"workspace_id": workspace_id, "index": idx})
            if action_id is None:
                continue
            rows.append(self._read_action(int(action_id)))
        return rows

    def create_workspace(self, payload: CreateWorkspaceInput, *, caller: str) -> tuple[WorkspaceRecord, ChainTxReceipt]:
        _ = caller
        receipt = self._exec("create_workspace", {"name": payload.name, "metadata_hash": payload.metadata_hash})
        workspace_id = int(self._read_value("workspace_nonce", {}))
        return self._read_workspace(workspace_id), receipt

    def add_member(self, payload: AddMemberInput, *, caller: str) -> tuple[MemberRecord, ChainTxReceipt]:
        _ = caller
        receipt = self._exec(
            "add_member",
            {
                "workspace_id": payload.workspace_id,
                "account": payload.account,
                "role": payload.role.name.title(),
            },
        )
        role = self._read_member_role(payload.workspace_id, payload.account)
        record = MemberRecord(workspace_id=payload.workspace_id, account=payload.account, role=role)
        return record, receipt

    def issue_credential(
        self, payload: IssueCredentialInput, *, caller: str
    ) -> tuple[CredentialRecord, ChainTxReceipt]:
        _ = caller
        receipt = self._exec(
            "issue_credential",
            {
                "workspace_id": payload.workspace_id,
                "account": payload.account,
                "credential_type": payload.credential_type,
                "credential_hash": payload.credential_hash,
            },
        )
        credential_id = int(self._read_value("credential_nonce", {}))
        return self._read_credential(credential_id), receipt

    def create_action(self, payload: CreateActionInput, *, caller: str) -> tuple[ActionRecord, ChainTxReceipt]:
        _ = caller
        receipt = self._exec(
            "create_action",
            {
                "workspace_id": payload.workspace_id,
                "action_type": payload.action_type,
                "payload_hash": payload.payload_hash,
                "required_role": payload.required_role.name.title(),
                "min_approvals": payload.min_approvals,
            },
        )
        action_id = int(self._read_value("action_nonce", {}))
        return self._read_action(action_id), receipt

    def approve_action(self, payload: ApproveActionInput, *, caller: str) -> tuple[ActionRecord, ChainTxReceipt]:
        _ = caller
        receipt = self._exec("approve_action", {"action_id": payload.action_id})
        return self._read_action(payload.action_id), receipt

    def execute_action(self, payload: ExecuteActionInput, *, caller: str) -> tuple[ActionRecord, ChainTxReceipt]:
        _ = caller
        receipt = self._exec("execute_action", {"action_id": payload.action_id})
        return self._read_action(payload.action_id), receipt

    def revoke_credential(
        self, payload: RevokeCredentialInput, *, caller: str
    ) -> tuple[CredentialRecord, ChainTxReceipt]:
        _ = caller
        receipt = self._exec("revoke_credential", {"credential_id": payload.credential_id})
        return self._read_credential(payload.credential_id), receipt


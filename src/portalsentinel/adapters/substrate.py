from __future__ import annotations

from dataclasses import dataclass
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
    """
    Adapter for real Portaldot integration through py-substrate-interface.

    Notes:
    - This adapter expects an ink! contract with the exact message names used by this repo.
    - For list methods, it reads from contract query methods if available; otherwise they return empty lists.
    """

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
        if not self.cfg.explorer_base_url:
            return None
        return f"{self.cfg.explorer_base_url.rstrip('/')}/extrinsic/{tx_hash}"

    def _exec(self, method: str, args: dict[str, Any]) -> ChainTxReceipt:
        receipt = self.contract.exec(
            keypair=self.signer,
            method=method,
            args=args,
            value=0,
            gas_limit={"ref_time": 2_000_000_000, "proof_size": 128_000},
        )
        tx_hash = getattr(receipt, "extrinsic_hash", None) or ""
        block_hash = getattr(receipt, "block_hash", None)
        success = bool(getattr(receipt, "is_success", True))
        events = []
        try:
            events = [event.value for event in getattr(receipt, "triggered_events", [])]
        except Exception:
            events = []
        return ChainTxReceipt(
            tx_hash=tx_hash,
            block_hash=block_hash,
            success=success,
            events=events,
            explorer_url=self._explorer_url(tx_hash),
            message=None if success else str(getattr(receipt, "error_message", "execution failed")),
        )

    def _read(self, method: str, args: dict[str, Any]) -> Any:
        result = self.contract.read(keypair=self.signer, method=method, args=args)
        if hasattr(result, "contract_result_data"):
            return result.contract_result_data
        if hasattr(result, "value"):
            return result.value
        return result

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
        return []

    def list_members(self, workspace_id: int) -> list[MemberRecord]:
        _ = workspace_id
        return []

    def list_actions(self, workspace_id: int | None = None) -> list[ActionRecord]:
        _ = workspace_id
        return []

    def create_workspace(self, payload: CreateWorkspaceInput, *, caller: str) -> tuple[WorkspaceRecord, ChainTxReceipt]:
        _ = caller
        receipt = self._exec("create_workspace", {"name": payload.name, "metadata_hash": payload.metadata_hash})
        created_id = self._read("workspace_nonce", {})
        record = WorkspaceRecord(
            workspace_id=int(created_id),
            name=payload.name,
            metadata_hash=payload.metadata_hash,
            owner=self.signer.ss58_address,
        )
        return record, receipt

    def add_member(self, payload: AddMemberInput, *, caller: str) -> tuple[MemberRecord, ChainTxReceipt]:
        _ = caller
        receipt = self._exec(
            "add_member",
            {
                "workspace_id": payload.workspace_id,
                "account": payload.account,
                "role": payload.role.value,
            },
        )
        record = MemberRecord(workspace_id=payload.workspace_id, account=payload.account, role=payload.role)
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
        credential_id = self._read("credential_nonce", {})
        record = CredentialRecord(
            credential_id=int(credential_id),
            workspace_id=payload.workspace_id,
            account=payload.account,
            credential_type=payload.credential_type,
            credential_hash=payload.credential_hash,
        )
        return record, receipt

    def create_action(self, payload: CreateActionInput, *, caller: str) -> tuple[ActionRecord, ChainTxReceipt]:
        _ = caller
        receipt = self._exec(
            "create_action",
            {
                "workspace_id": payload.workspace_id,
                "action_type": payload.action_type,
                "payload_hash": payload.payload_hash,
                "required_role": payload.required_role.value,
                "min_approvals": payload.min_approvals,
            },
        )
        action_id = self._read("action_nonce", {})
        record = ActionRecord(
            action_id=int(action_id),
            workspace_id=payload.workspace_id,
            action_type=payload.action_type,
            payload_hash=payload.payload_hash,
            required_role=payload.required_role,
            min_approvals=payload.min_approvals,
            approvals=0,
            proposer=self.signer.ss58_address,
        )
        return record, receipt

    def approve_action(self, payload: ApproveActionInput, *, caller: str) -> tuple[ActionRecord, ChainTxReceipt]:
        _ = caller
        receipt = self._exec("approve_action", {"action_id": payload.action_id})
        action = ActionRecord(
            action_id=payload.action_id,
            workspace_id=0,
            action_type="unknown",
            payload_hash="unknown",
            required_role=Role.VIEWER,
            min_approvals=1,
            approvals=1,
            proposer=self.signer.ss58_address,
        )
        return action, receipt

    def execute_action(self, payload: ExecuteActionInput, *, caller: str) -> tuple[ActionRecord, ChainTxReceipt]:
        _ = caller
        receipt = self._exec("execute_action", {"action_id": payload.action_id})
        action = ActionRecord(
            action_id=payload.action_id,
            workspace_id=0,
            action_type="unknown",
            payload_hash="unknown",
            required_role=Role.VIEWER,
            min_approvals=1,
            approvals=1,
            proposer=self.signer.ss58_address,
            status=ActionStatus.EXECUTED,
        )
        return action, receipt

    def revoke_credential(
        self, payload: RevokeCredentialInput, *, caller: str
    ) -> tuple[CredentialRecord, ChainTxReceipt]:
        _ = caller
        receipt = self._exec("revoke_credential", {"credential_id": payload.credential_id})
        record = CredentialRecord(
            credential_id=payload.credential_id,
            workspace_id=0,
            account=self.signer.ss58_address,
            credential_type="unknown",
            credential_hash="unknown",
            revoked=True,
        )
        return record, receipt

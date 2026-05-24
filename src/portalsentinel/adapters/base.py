from __future__ import annotations

from abc import ABC, abstractmethod

from portalsentinel.models import (
    ActionRecord,
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
    WorkspaceRecord,
)


class ChainAdapter(ABC):
    @abstractmethod
    def health(self) -> ChainHealth:
        raise NotImplementedError

    @abstractmethod
    def list_workspaces(self) -> list[WorkspaceRecord]:
        raise NotImplementedError

    @abstractmethod
    def list_members(self, workspace_id: int) -> list[MemberRecord]:
        raise NotImplementedError

    @abstractmethod
    def list_actions(self, workspace_id: int | None = None) -> list[ActionRecord]:
        raise NotImplementedError

    @abstractmethod
    def create_workspace(self, payload: CreateWorkspaceInput, *, caller: str) -> tuple[WorkspaceRecord, ChainTxReceipt]:
        raise NotImplementedError

    @abstractmethod
    def add_member(self, payload: AddMemberInput, *, caller: str) -> tuple[MemberRecord, ChainTxReceipt]:
        raise NotImplementedError

    @abstractmethod
    def issue_credential(
        self, payload: IssueCredentialInput, *, caller: str
    ) -> tuple[CredentialRecord, ChainTxReceipt]:
        raise NotImplementedError

    @abstractmethod
    def create_action(self, payload: CreateActionInput, *, caller: str) -> tuple[ActionRecord, ChainTxReceipt]:
        raise NotImplementedError

    @abstractmethod
    def approve_action(self, payload: ApproveActionInput, *, caller: str) -> tuple[ActionRecord, ChainTxReceipt]:
        raise NotImplementedError

    @abstractmethod
    def execute_action(self, payload: ExecuteActionInput, *, caller: str) -> tuple[ActionRecord, ChainTxReceipt]:
        raise NotImplementedError

    @abstractmethod
    def revoke_credential(
        self, payload: RevokeCredentialInput, *, caller: str
    ) -> tuple[CredentialRecord, ChainTxReceipt]:
        raise NotImplementedError


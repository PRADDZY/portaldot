from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Role(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    CONTRIBUTOR = "contributor"
    VIEWER = "viewer"


class ActionStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    EXECUTED = "executed"
    REVOKED = "revoked"


class ChainTxReceipt(BaseModel):
    tx_hash: str
    success: bool = True
    block_hash: str | None = None
    fee: int | None = None
    explorer_url: str | None = None
    events: list[dict[str, Any]] = Field(default_factory=list)
    message: str | None = None


class ChainHealth(BaseModel):
    mode: Literal["mock", "substrate"]
    connected: bool
    node: str
    details: dict[str, Any] = Field(default_factory=dict)


class WorkspaceRecord(BaseModel):
    workspace_id: int
    name: str
    metadata_hash: str
    owner: str
    created_at: str = Field(default_factory=utc_now_iso)


class MemberRecord(BaseModel):
    workspace_id: int
    account: str
    role: Role
    added_at: str = Field(default_factory=utc_now_iso)


class CredentialRecord(BaseModel):
    credential_id: int
    workspace_id: int
    account: str
    credential_type: str
    credential_hash: str
    revoked: bool = False
    created_at: str = Field(default_factory=utc_now_iso)


class ActionRecord(BaseModel):
    action_id: int
    workspace_id: int
    action_type: str
    payload_hash: str
    required_role: Role
    min_approvals: int = Field(default=1, ge=1)
    approvals: int = 0
    status: ActionStatus = ActionStatus.PENDING
    proposer: str
    created_at: str = Field(default_factory=utc_now_iso)
    executed_at: str | None = None


class CreateWorkspaceInput(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    metadata_hash: str = Field(min_length=2, max_length=256)


class AddMemberInput(BaseModel):
    workspace_id: int = Field(ge=1)
    account: str = Field(min_length=10, max_length=128)
    role: Role


class IssueCredentialInput(BaseModel):
    workspace_id: int = Field(ge=1)
    account: str = Field(min_length=10, max_length=128)
    credential_type: str = Field(min_length=2, max_length=64)
    credential_hash: str = Field(min_length=2, max_length=256)


class CreateActionInput(BaseModel):
    workspace_id: int = Field(ge=1)
    action_type: str = Field(min_length=2, max_length=64)
    payload_hash: str = Field(min_length=2, max_length=256)
    required_role: Role
    min_approvals: int = Field(default=1, ge=1, le=10)


class ApproveActionInput(BaseModel):
    action_id: int = Field(ge=1)


class ExecuteActionInput(BaseModel):
    action_id: int = Field(ge=1)


class RevokeCredentialInput(BaseModel):
    credential_id: int = Field(ge=1)


class AgentActionStep(BaseModel):
    action: Literal[
        "create_workspace",
        "add_member",
        "issue_credential",
        "create_action",
        "approve_action",
        "execute_action",
        "revoke_credential",
    ]
    params: dict[str, Any] = Field(default_factory=dict)
    reason: str = Field(default="", max_length=300)


class ActionPlan(BaseModel):
    plan_id: str = Field(default_factory=lambda: str(uuid4()))
    intent: str
    workspace_id: int | None = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    assumptions: list[str] = Field(default_factory=list)
    steps: list[AgentActionStep] = Field(default_factory=list)

    @field_validator("steps")
    @classmethod
    def must_have_steps(cls, value: list[AgentActionStep]) -> list[AgentActionStep]:
        if not value:
            raise ValueError("plan must contain at least one step")
        return value


class PlanRequest(BaseModel):
    intent: str = Field(min_length=5, max_length=2000)
    workspace_id: int | None = Field(default=None, ge=1)
    dry_run: bool = True


class SimulateRequest(BaseModel):
    plan: ActionPlan


class SubmitRequest(BaseModel):
    plan: ActionPlan
    confirm: bool = False
    caller: str = Field(default="demo-caller")


class SessionRecord(BaseModel):
    session_id: str
    mode: str
    intent: str
    status: str
    created_at: str
    updated_at: str
    plan: ActionPlan | None = None


class EventRecord(BaseModel):
    event_id: int
    session_id: str | None = None
    source: str
    event_type: str
    payload: dict[str, Any]
    created_at: str


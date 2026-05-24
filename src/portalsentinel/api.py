from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from portalsentinel.models import (
    AddMemberInput,
    ApproveActionInput,
    CreateActionInput,
    CreateWorkspaceInput,
    ExecuteActionInput,
    IssueCredentialInput,
    PlanRequest,
    RevokeCredentialInput,
    SimulateRequest,
    SubmitRequest,
)
from portalsentinel.service import PortalService


def make_router(service: PortalService) -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    def health() -> dict:
        return service.health()

    @router.get("/workspaces")
    def workspaces() -> dict:
        return {"items": service.list_workspaces()}

    @router.get("/workspaces/{workspace_id}/members")
    def members(workspace_id: int) -> dict:
        try:
            return {"items": service.list_members(workspace_id)}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/actions")
    def actions(workspace_id: int | None = Query(default=None, ge=1)) -> dict:
        try:
            return {"items": service.list_actions(workspace_id)}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/workspaces")
    def create_workspace(payload: CreateWorkspaceInput, caller: str = Query(default="demo-caller")) -> dict:
        try:
            return service.create_workspace(payload, caller=caller)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/members")
    def add_member(payload: AddMemberInput, caller: str = Query(default="demo-caller")) -> dict:
        try:
            return service.add_member(payload, caller=caller)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/credentials")
    def issue_credential(payload: IssueCredentialInput, caller: str = Query(default="demo-caller")) -> dict:
        try:
            return service.issue_credential(payload, caller=caller)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/actions")
    def create_action(payload: CreateActionInput, caller: str = Query(default="demo-caller")) -> dict:
        try:
            return service.create_action(payload, caller=caller)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/actions/approve")
    def approve_action(payload: ApproveActionInput, caller: str = Query(default="demo-caller")) -> dict:
        try:
            return service.approve_action(payload, caller=caller)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/actions/execute")
    def execute_action(payload: ExecuteActionInput, caller: str = Query(default="demo-caller")) -> dict:
        try:
            return service.execute_action(payload, caller=caller)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/credentials/revoke")
    def revoke_credential(payload: RevokeCredentialInput, caller: str = Query(default="demo-caller")) -> dict:
        try:
            return service.revoke_credential(payload, caller=caller)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/agent/plan")
    def plan(payload: PlanRequest) -> dict:
        try:
            return service.plan(payload)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/agent/simulate")
    def simulate(payload: SimulateRequest) -> dict:
        try:
            return service.simulate(payload)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/agent/submit")
    def submit(payload: SubmitRequest) -> dict:
        try:
            return service.submit(payload)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/events")
    def events(session_id: str | None = None, limit: int = Query(default=200, ge=1, le=1000)) -> dict:
        return {"items": [row.model_dump() for row in service.store.list_events(session_id=session_id, limit=limit)]}

    @router.get("/sessions")
    def sessions(limit: int = Query(default=100, ge=1, le=500)) -> dict:
        return {"items": [row.model_dump() for row in service.store.list_sessions(limit=limit)]}

    return router

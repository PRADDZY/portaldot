from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import httpx

from portalsentinel.config import Settings
from portalsentinel.models import ActionPlan, AgentActionStep, PlanRequest, Role


class AIPlanner:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.schema_path = Path(__file__).resolve().parents[2] / "packages" / "shared-schemas" / "action-plan.schema.json"

    def build_plan(self, request: PlanRequest) -> ActionPlan:
        # Always keep a deterministic fallback to protect demo reliability.
        fallback = self._fallback_plan(request)
        if not self.settings.openrouter_api_key:
            return fallback

        try:
            ai_plan = self._from_openrouter(request)
            return ai_plan
        except Exception:
            return fallback

    def _from_openrouter(self, request: PlanRequest) -> ActionPlan:
        schema = self.schema_path.read_text(encoding="utf-8")
        prompt = (
            "You are a planning assistant for an onchain workflow CLI.\n"
            "Return strict JSON only. No markdown.\n"
            "Use this schema exactly:\n"
            f"{schema}\n\n"
            "Allowed actions: create_workspace, add_member, issue_credential, create_action, approve_action, "
            "execute_action, revoke_credential.\n"
            f"Intent: {request.intent}\n"
            f"Workspace ID: {request.workspace_id}\n"
            "Set confidence to a realistic value between 0 and 1."
        )
        headers = {
            "Authorization": f"Bearer {self.settings.openrouter_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.settings.openrouter_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }
        with httpx.Client(timeout=45) as client:
            response = client.post(f"{self.settings.openrouter_base_url.rstrip('/')}/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        content = data["choices"][0]["message"]["content"]
        raw = self._extract_json(content)
        parsed = json.loads(raw)
        return ActionPlan.model_validate(parsed)

    def _extract_json(self, text: str) -> str:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
            cleaned = re.sub(r"```$", "", cleaned).strip()
        return cleaned

    def _fallback_plan(self, request: PlanRequest) -> ActionPlan:
        intent_lower = request.intent.lower()
        workspace_id = request.workspace_id
        assumptions: list[str] = []
        steps: list[AgentActionStep] = []

        if workspace_id is None:
            assumptions.append("No workspace_id supplied; first step creates a workspace.")
            steps.append(
                AgentActionStep(
                    action="create_workspace",
                    params={
                        "name": "PortalSentinel Workspace",
                        "metadata_hash": "ipfs://demo-workspace-metadata",
                    },
                    reason="A workspace is required for identity and action state.",
                )
            )

        if "member" in intent_lower or "team" in intent_lower or "onboard" in intent_lower:
            steps.append(
                AgentActionStep(
                    action="add_member",
                    params={
                        "workspace_id": workspace_id,
                        "account": "5DemoMember111111111111111111111111111111111",
                        "role": Role.CONTRIBUTOR.value,
                    },
                    reason="Onboarding workflow should include membership assignment.",
                )
            )

        if "credential" in intent_lower or "badge" in intent_lower or "identity" in intent_lower:
            steps.append(
                AgentActionStep(
                    action="issue_credential",
                    params={
                        "workspace_id": workspace_id,
                        "account": "5DemoMember111111111111111111111111111111111",
                        "credential_type": "contributor_badge",
                        "credential_hash": "ipfs://demo-credential",
                    },
                    reason="Identity-focused intent should mint a verifiable credential.",
                )
            )

        steps.append(
            AgentActionStep(
                action="create_action",
                params={
                    "workspace_id": workspace_id,
                    "action_type": "grant_disbursement",
                    "payload_hash": "ipfs://demo-action-payload",
                    "required_role": Role.ADMIN.value,
                    "min_approvals": 1,
                },
                reason="Each workflow should produce an actionable onchain intent.",
            )
        )
        steps.append(
            AgentActionStep(
                action="approve_action",
                params={"action_id": None},
                reason="Approval step proves role-gated coordination.",
            )
        )
        steps.append(
            AgentActionStep(
                action="execute_action",
                params={"action_id": None},
                reason="Execution closes the workflow loop for demo completeness.",
            )
        )

        return ActionPlan(
            intent=request.intent,
            workspace_id=workspace_id,
            confidence=0.62,
            assumptions=assumptions,
            steps=steps,
        )


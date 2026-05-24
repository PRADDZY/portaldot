# Judging Criteria Mapping

## Portaldot Native Deployment (Mandatory)
- ink! smart contract in `contracts/identity-workflow-registry`.
- Substrate integration path in `src/portalsentinel/adapters/substrate.py`.
- Configurable Portaldot websocket + contract address + signer settings.
- Real onchain list/read paths via contract enumeration methods (`workspace_count`, `member_count`, `action_count`, etc.).

## Demo Completion
- CLI path: `plan -> simulate -> submit -> replay`.
- API path with event/session endpoints.
- Dashboard path for visual replay.
- Deterministic evidence artifacts from scripts (`evidence-latest.json`, `failure-scenario.json`).

## Application Value
- Solves role and approval friction for builder teams using onchain workflows.
- Converts natural-language intent into auditable execution steps.

## Presentation Quality
- Clear 4-5 minute script in `docs/demo/demo-script.md`.
- Structured event timeline and session replay artifacts.
- Includes one explicit failure-path recovery to show robustness.

## Community Voting (Separate)
- Optional public dashboard deployment and short demo clip extraction.


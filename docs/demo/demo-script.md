# Demo Script (4-5 min)

## 0) Setup framing (20s)
- Show project title and one-line pitch.
- State this is a Portaldot-native identity + workflow orchestration MVP.

## 1) Environment and readiness (30s)
- Run `python ./scripts/check_ready.py --mode all`.
- If showing live substrate flow, also run `python ./scripts/check_ready.py --mode contract`.
- Run `portalctl health`.
- Mention current mode (`mock` or `substrate`) and contract configuration.

## 2) End-to-end success flow (90s)
- Run `python ./scripts/e2e_workflow.py`.
- Show generated `docs/submission/evidence-latest.json`.
- Highlight `action.created -> action.approved -> action.executed`.

## 3) Failure-path proof (60s)
- Run `python ./scripts/failure_scenario.py`.
- Show expected guardrail error from `docs/submission/failure-scenario.json`.
- Explain why this protects real workflows.

## 4) Replay and UI evidence (60s)
- Open API `/events` and `/sessions`, or run `portalctl replay session --id <session-id>`.
- Open dashboard timeline and show matching events.
- If in substrate mode, show tx hashes and explorer links.

## 5) Close (30s)
- Summarize value: role-safe coordination + auditable automation.
- Point to open-source contract and submission checklist.

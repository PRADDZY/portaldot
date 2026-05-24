# Demo Script (4–5 min)

## 0) Setup framing (20s)
- Show project title and one-line pitch.
- State this is a Portaldot-native identity + workflow orchestration MVP.

## 1) Chain and system health (30s)
- Run `portalctl health`.
- Open API `/health`.
- Mention current mode (`mock` or `substrate`) and contract configuration.

## 2) Identity flow (60s)
- Create workspace.
- Add contributor/admin member.
- Issue credential.
- Show resulting events in `/events` or dashboard stream.

## 3) Agent workflow loop (90s)
- Generate plan with `portalctl agent plan`.
- Simulate with `portalctl agent simulate` (show guardrails pass).
- Submit with `portalctl agent submit --confirm`.

## 4) Approval and execution proof (60s)
- Highlight `action.created -> action.approved -> action.executed` sequence.
- Show session replay by ID.
- If in substrate mode, show tx hash and explorer URL.

## 5) Close (30s)
- Summarize market value: role-safe coordination and faster onchain operations.
- Show repo structure and open-source contract path.


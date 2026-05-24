# How PortalSentinel Uses Portaldot (Submission Draft)

PortalSentinel is built natively for a Substrate/ink! flow on Portaldot.

## Onchain contract layer
- Contract: `contracts/identity-workflow-registry/src/lib.rs`
- Language/runtime: Rust + ink! (non-EVM)
- Core messages used in demo:
  - `create_workspace`
  - `add_member`
  - `issue_credential`
  - `create_action`
  - `approve_action`
  - `execute_action`
  - `revoke_credential`

## Portaldot-native execution
- Transactions are submitted through Substrate RPC (`PORTALDOT_WS`).
- Contract calls are signed with a Substrate keypair (`DEMO_SIGNER_URI`).
- Receipts include extrinsic hash, block hash, and event payloads.
- If `PORTALDOT_EXPLORER_BASE_URL` is set, explorer links are emitted in responses.

## Workflow evidence to include in form
- `docs/submission/evidence-latest.json` from `python ./scripts/e2e_workflow.py`
- `docs/submission/failure-scenario.json` from `python ./scripts/failure_scenario.py`
- Demo video section showing tx hashes and approval/execution transitions.

## POT gas proof
- In substrate mode, every state-changing action emits receipt data with transaction identity.
- Capture and include at least one successful action tx hash and explorer URL in final submission text.


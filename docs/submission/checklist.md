# Submission Checklist

## Required fields
- [ ] Project Name
- [ ] Public Repository Link
- [ ] Demo Video Link
- [ ] How Does Your Project Use Portaldot?

## Repository quality
- [ ] README explains setup, architecture, and demo flow
- [ ] Core smart contract is open source
- [ ] No secrets committed (`.env` ignored)
- [ ] Commands run from clean checkout
- [ ] `python ./scripts/check_ready.py --mode all` passes
- [ ] If demonstrating substrate mode: `python ./scripts/check_ready.py --mode contract` passes

## Demo quality
- [ ] Runnable MVP
- [ ] End-to-end identity + action workflow shown
- [ ] Replay/evidence view shown (CLI session replay and/or dashboard)
- [ ] Failure handling demonstrated once (invalid approval or missing permissions)
- [ ] `python ./scripts/e2e_workflow.py` generated `docs/submission/evidence-latest.json`
- [ ] `python ./scripts/failure_scenario.py` generated `docs/submission/failure-scenario.json`

## Portaldot-native proof
- [ ] Contract deployment details captured
- [ ] POT gas usage evidence (tx receipt/explorer)
- [ ] Non-EVM design rationale stated

## Security and dependency hygiene
- [ ] Critical/high dependency issues reviewed and patched where possible
- [ ] No API keys or private signer seeds committed

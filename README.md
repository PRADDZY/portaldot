# PortalSentinel

PortalSentinel is a CLI-first identity and approval workflow orchestrator built for **Portaldot Online Mini Hackathon S1**.

It proves a full loop:
- identity and membership state,
- action proposal and role-gated approvals,
- final execution with event replay for judges.

## Why this fits the hackathon

- Built for Portaldot-native workflow patterns.
- Designed around a **runnable MVP** and a clear demo path.
- Keeps **core contract open source**.
- Includes required submission surfaces: repo-ready code, README-ready architecture, and demo script.

## Repository layout

```text
contracts/identity-workflow-registry/   # ink! contract
apps/api/                               # API entrypoint wrapper
apps/portalctl/                         # CLI entrypoint wrapper
apps/dashboard/                         # judge replay dashboard (Next.js)
packages/shared-schemas/                # JSON schema for AI action plans
src/portalsentinel/                     # Python core (API, CLI, planner, adapters, store)
tests/python/                           # pytest coverage for workflow lifecycle
scripts/                                # readiness, contract build, e2e, reset helpers
docs/demo/                              # demo script and run order
docs/submission/                        # submission checklist and mapping to judging criteria
```

## Quickstart

### 1) Python backend + CLI

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
```

Start API:

```powershell
portalsentinel-api
```

Run CLI health:

```powershell
portalctl health
```

### 2) Dashboard (optional but recommended for judges)

```powershell
cd apps/dashboard
npm install
$env:NEXT_PUBLIC_API_BASE="http://localhost:8000"
npm run dev
```

Open `http://localhost:3000`.

## CLI workflow

Create a workspace:

```powershell
portalctl workspace create --name "Hack Team" --metadata-hash "ipfs://team-meta" --caller alice
```

Add a member:

```powershell
portalctl member add --workspace-id 1 --account 5DemoMember111111111111111111111111111111111 --role contributor --caller alice
```

Issue credential:

```powershell
portalctl credential issue --workspace-id 1 --account 5DemoMember111111111111111111111111111111111 --credential-type contributor_badge --credential-hash ipfs://cred-1 --caller alice
```

Create/approve/execute action:

```powershell
portalctl action create --workspace-id 1 --action-type grant_disbursement --payload-hash ipfs://grant-1 --required-role admin --min-approvals 1 --caller alice
portalctl action approve --action-id 1 --caller alice
portalctl action execute --action-id 1 --caller alice
```

Agent plan/simulate/submit:

```powershell
portalctl agent plan --intent "onboard member and run grant workflow" --out data/plan.json
portalctl agent simulate --plan-file data/plan.json
portalctl agent submit --plan-file data/plan.json --confirm --caller alice
```

Replay:

```powershell
portalctl replay session --id <session-id>
```

## API endpoints

- `GET /health`
- `GET /workspaces`
- `GET /workspaces/{workspace_id}/members`
- `GET /actions?workspace_id=`
- `POST /workspaces`
- `POST /members`
- `POST /credentials`
- `POST /credentials/revoke`
- `POST /actions`
- `POST /actions/approve`
- `POST /actions/execute`
- `POST /agent/plan`
- `POST /agent/simulate`
- `POST /agent/submit`
- `GET /events`
- `GET /sessions`

## Portaldot integration mode

Default is `CHAIN_MODE=mock` for local reliability.

To use a live chain:
- set `CHAIN_MODE=substrate`,
- deploy the ink! contract and set `CONTRACT_ADDRESS`,
- provide compiled metadata file at `CONTRACT_METADATA_PATH`,
- set signer via `DEMO_SIGNER_URI`.

Toolchain + contract artifact commands:

```powershell
pwsh ./scripts/install_vs_buildtools.ps1
pwsh ./scripts/setup_rust_toolchain.ps1
pwsh ./scripts/build_contract.ps1
python ./scripts/check_ready.py --mode all
python ./scripts/check_ready.py --mode contract
python ./scripts/check_ready.py --mode live
```

Notes:
- `--mode all` validates the default app/demo path and warns if contract-only tooling is missing.
- `--mode contract` is strict and should pass before a substrate-mode demo.
- `--mode live` validates substrate env + RPC reachability for live chain execution.
- Windows contract builds require Visual Studio Build Tools (C++/MSVC `link.exe`).

Live substrate deploy + smoke commands:

```powershell
pwsh ./scripts/deploy_contract.ps1
$env:CHAIN_MODE="substrate"
python ./scripts/check_ready.py --mode live
python ./scripts/live_substrate_smoke.py
```

## Contract

Contract path:
- `contracts/identity-workflow-registry/src/lib.rs`

Contract methods:
- `create_workspace`
- `add_member`
- `issue_credential`
- `create_action`
- `approve_action`
- `execute_action`
- `revoke_credential`
- getters: `get_workspace`, `get_member_role`, `get_credential`, `get_action`
- enumeration: `workspace_count`, `workspace_id_at`, `member_count`, `member_at`, `action_count`, `action_id_at`, `workspace_action_count`, `workspace_action_id_at`

## Tests

Python tests:

```powershell
pytest -q tests/python
```

Contract unit tests are embedded in:
- `contracts/identity-workflow-registry/src/lib.rs`

Operational checks and evidence capture:

```powershell
python ./scripts/check_ready.py --mode all
python ./scripts/check_ready.py --mode contract
python ./scripts/e2e_workflow.py
python ./scripts/failure_scenario.py
python ./scripts/demo_reset.py --purge-evidence
```

## Demo and submission docs

- Demo runbook: [docs/demo/demo-script.md](docs/demo/demo-script.md)
- Submission checklist: [docs/submission/checklist.md](docs/submission/checklist.md)
- Judging mapping: [docs/submission/judging-map.md](docs/submission/judging-map.md)
- Portaldot usage draft: [docs/submission/how-it-uses-portaldot.md](docs/submission/how-it-uses-portaldot.md)

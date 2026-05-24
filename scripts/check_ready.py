from __future__ import annotations

import argparse
import json
import platform
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from portalsentinel.config import Settings  # noqa: E402

try:
    from substrateinterface import SubstrateInterface
except Exception:  # pragma: no cover - import guard for local env without substrate deps
    SubstrateInterface = None


def _candidate_executable(path: Path, name: str) -> Path:
    if platform.system().lower().startswith("win") and not name.lower().endswith(".exe"):
        return path / f"{name}.exe"
    return path / name


def check_tool(name: str) -> tuple[bool, str]:
    resolved = shutil.which(name)
    if not resolved:
        cargo_bin = Path.home() / ".cargo" / "bin"
        fallback = _candidate_executable(cargo_bin, name)
        if fallback.exists():
            return True, f"{fallback} (found outside PATH)"
        return False, f"{name} not found in PATH"
    return True, resolved


def check_substrate_rpc(ws_url: str) -> tuple[bool, dict[str, str]]:
    if SubstrateInterface is None:
        return False, {"error": "substrate-interface dependency is unavailable"}

    substrate = None
    try:
        substrate = SubstrateInterface(url=ws_url)
        chain = str((substrate.rpc_request("system_chain", []) or {}).get("result", "unknown"))
        node = str((substrate.rpc_request("system_name", []) or {}).get("result", "unknown"))
        return True, {"chain": chain, "node": node}
    except Exception as exc:
        return False, {"error": str(exc)}
    finally:
        if substrate is not None:
            try:
                substrate.close()
            except Exception:
                pass


def run(check_mode: str) -> int:
    settings = Settings()
    errors: list[str] = []
    warnings: list[str] = []

    output: dict[str, object] = {
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "chain_mode": settings.chain_mode,
        "checks": {},
    }

    py_ok = sys.version_info >= (3, 11)
    output["checks"]["python>=3.11"] = py_ok
    if not py_ok:
        errors.append("Python 3.11+ required")

    for tool in ("node", "npm"):
        ok, detail = check_tool(tool)
        output["checks"][tool] = {"ok": ok, "detail": detail}
        if not ok:
            warnings.append(detail)

    require_contract_tooling = check_mode in ("contract", "live") or settings.chain_mode == "substrate"
    output["checks"]["contract_tooling_required"] = require_contract_tooling

    if check_mode in ("all", "contract", "live"):
        for tool in ("cargo", "cargo-contract", "rustup"):
            ok, detail = check_tool(tool)
            output["checks"][tool] = {"ok": ok, "detail": detail}
            if not ok and require_contract_tooling:
                errors.append(detail)
            elif not ok:
                warnings.append(f"{detail} (required for contract/substrate mode)")

    metadata_path = None
    if settings.contract_metadata_path:
        metadata_path = Path(settings.contract_metadata_path)
        if not metadata_path.is_absolute():
            metadata_path = ROOT / metadata_path
        exists = metadata_path.exists()
        output["checks"]["contract_metadata"] = {"ok": exists, "path": str(metadata_path)}
        if require_contract_tooling and check_mode in ("all", "contract", "substrate", "live") and not exists:
            errors.append(f"Contract metadata missing: {metadata_path}")

    if settings.chain_mode == "substrate":
        if not settings.contract_address:
            errors.append("CONTRACT_ADDRESS is required in substrate mode")
        if not settings.portaldot_ws:
            errors.append("PORTALDOT_WS is required in substrate mode")

    if check_mode == "live":
        if settings.chain_mode != "substrate":
            errors.append("CHAIN_MODE must be 'substrate' for --mode live")
        if not settings.contract_address:
            errors.append("CONTRACT_ADDRESS is required for --mode live")
        if not settings.portaldot_ws:
            errors.append("PORTALDOT_WS is required for --mode live")
        if not settings.signer_uri:
            errors.append("DEMO_SIGNER_URI is required for --mode live")

        if settings.portaldot_ws:
            rpc_ok, rpc_details = check_substrate_rpc(settings.portaldot_ws)
            output["checks"]["substrate_rpc"] = {"ok": rpc_ok, **rpc_details}
            if not rpc_ok:
                errors.append(f"Unable to reach substrate RPC: {rpc_details.get('error', 'unknown error')}")

    output["errors"] = errors
    output["warnings"] = warnings
    print(json.dumps(output, indent=2))
    return 1 if errors else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="PortalSentinel readiness checks")
    parser.add_argument(
        "--mode",
        choices=("all", "contract", "substrate", "live"),
        default="all",
        help="Validation scope",
    )
    args = parser.parse_args()
    return run(args.mode)


if __name__ == "__main__":
    raise SystemExit(main())

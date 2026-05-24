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

    require_contract_tooling = check_mode == "contract" or settings.chain_mode == "substrate"
    output["checks"]["contract_tooling_required"] = require_contract_tooling

    if check_mode in ("all", "contract"):
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
        if require_contract_tooling and check_mode in ("all", "contract", "substrate") and not exists:
            errors.append(f"Contract metadata missing: {metadata_path}")

    if settings.chain_mode == "substrate":
        if not settings.contract_address:
            errors.append("CONTRACT_ADDRESS is required in substrate mode")
        if not settings.portaldot_ws:
            errors.append("PORTALDOT_WS is required in substrate mode")

    output["errors"] = errors
    output["warnings"] = warnings
    print(json.dumps(output, indent=2))
    return 1 if errors else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="PortalSentinel readiness checks")
    parser.add_argument(
        "--mode",
        choices=("all", "contract", "substrate"),
        default="all",
        help="Validation scope",
    )
    args = parser.parse_args()
    return run(args.mode)


if __name__ == "__main__":
    raise SystemExit(main())

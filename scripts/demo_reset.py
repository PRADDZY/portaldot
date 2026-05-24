from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from portalsentinel.config import Settings  # noqa: E402


def remove_if_exists(path: Path) -> bool:
    if path.exists():
        path.unlink()
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset local demo state")
    parser.add_argument(
        "--purge-evidence",
        action="store_true",
        help="Also delete docs/submission evidence artifacts if present",
    )
    args = parser.parse_args()

    settings = Settings()
    removed = []
    for path in (settings.storage_path, settings.data_dir / "mock_state.json"):
        absolute = path if path.is_absolute() else ROOT / path
        if remove_if_exists(absolute):
            removed.append(str(absolute))

    if args.purge_evidence:
        for evidence_name in ("evidence-latest.json", "failure-scenario.json"):
            evidence = ROOT / "docs" / "submission" / evidence_name
            if remove_if_exists(evidence):
                removed.append(str(evidence))

    if removed:
        print("Removed:")
        for row in removed:
            print(f"- {row}")
    else:
        print("No files removed (already clean).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

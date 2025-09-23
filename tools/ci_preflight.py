#!/usr/bin/env python3
"""Self-healing preflight import checker for CI workflows."""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path
from typing import Dict, Tuple


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent

# Ensure the repository root is the first entry on sys.path so third-party
# imports (notably numpy) resolve their compiled extensions correctly when this
# script is executed via ``python tools/ci_preflight.py``.
if sys.path and Path(sys.path[0]).resolve() == SCRIPT_DIR:
    sys.path.pop(0)
    sys.path.insert(0, str(REPO_ROOT))
elif str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


REQUIRED_MODULES = ("numpy", "pandas", "matplotlib")


def import_required_modules() -> Tuple[Dict[str, object], Dict[str, BaseException]]:
    """Attempt to import required modules.

    Returns a tuple of (loaded_modules, missing_modules).
    """

    loaded = {}
    missing = {}
    for name in REQUIRED_MODULES:
        try:
            loaded[name] = importlib.import_module(name)
        except Exception as exc:  # noqa: BLE001 - we want the original exception message.
            missing[name] = exc
    return loaded, missing


def install_requirements() -> None:
    """Install CI requirements using the current interpreter."""

    repo_root = Path(__file__).resolve().parent.parent
    requirements_file = repo_root / "requirements-ci.txt"
    if not requirements_file.is_file():
        raise FileNotFoundError(f"requirements file not found: {requirements_file}")

    print(f"Attempting to install dependencies from {requirements_file}...")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", str(requirements_file)],
        check=True,
    )


def main() -> int:
    loaded, missing = import_required_modules()

    if missing:
        print("Initial import check failed; missing modules detected:")
        for name, err in missing.items():
            print(f"  - {name}: {err}")
        try:
            install_requirements()
        except subprocess.CalledProcessError as exc:  # pragma: no cover - defensive for CI only.
            print("ERROR: Failed to install requirements-ci.txt via pip.")
            return exc.returncode or 1
        except FileNotFoundError as exc:  # pragma: no cover - defensive for CI only.
            print(f"ERROR: {exc}")
            return 1

        loaded, missing = import_required_modules()

    if missing:
        print("ERROR: Required Python modules are missing after reinstall attempt:")
        for name, err in missing.items():
            print(f"  - {name}: {err}")
        return 1

    print(f"Interpreter: {sys.executable}")
    print(f"Python: {sys.version}")
    print(
        "Resolved versions:",
        " ".join(
            f"{name}={getattr(module, '__version__', 'unknown')}"
            for name, module in loaded.items()
        ),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())


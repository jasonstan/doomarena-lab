"""Helpers for collecting run metadata."""
from __future__ import annotations

import hashlib
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


def _run_git_command(args: list[str]) -> str:
    try:
        result = subprocess.check_output(["git", *args], text=True, stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"
    value = result.strip()
    return value or "unknown"


def git_info() -> dict[str, str]:
    """Return the current git commit SHA and branch name."""
    commit = _run_git_command(["rev-parse", "HEAD"])
    branch = _run_git_command(["rev-parse", "--abbrev-ref", "HEAD"])
    return {"commit": commit, "branch": branch}


def _load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def cfg_hash(path: str | Path) -> str:
    """Return a stable SHA1 hash for the given YAML config file."""
    cfg_path = Path(path)
    try:
        data = _load_yaml(cfg_path)
    except (OSError, yaml.YAMLError):
        return "unknown"
    if data is None:
        data = {}
    dumped = yaml.safe_dump(data, sort_keys=True)
    digest = hashlib.sha1(dumped.encode("utf-8")).hexdigest()
    return digest


def now_iso() -> str:
    """Return the current UTC time in ISO-8601 format."""
    return datetime.utcnow().isoformat() + "Z"

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, MutableMapping, Sequence

import yaml

SUMMARY_COLUMNS: Sequence[str] = (
    "timestamp",
    "run_id",
    "git_sha",
    "git_branch",
    "repo_dirty",
    "exp",
    "exp_id",
    "seed",
    "mode",
    "trials",
    "successes",
    "asr",
    "python_version",
    "packages",
    "seeds",
    "path",
)

LEGACY_SUMMARY_COLUMNS: Sequence[str] = (
    "timestamp",
    "run_id",
    "git_sha",
    "repo_dirty",
    "exp",
    "seed",
    "mode",
    "trials",
    "successes",
    "asr",
    "py_version",
    "path",
)


def _normalize(value: Any) -> Any:
    if isinstance(value, dict):
        normalized: Dict[str, Any] = {}
        for key in sorted(value):
            normalized[str(key)] = _normalize(value[key])
        return normalized
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    if isinstance(value, tuple):
        return [_normalize(item) for item in value]
    if isinstance(value, Path):
        return value.as_posix()
    return value


def load_config(path: str | Path) -> Dict[str, Any]:
    cfg_path = Path(path)
    with cfg_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return _normalize(data)


def make_exp_id(cfg: MutableMapping[str, Any] | Dict[str, Any]) -> str:
    normalized = _normalize(cfg)
    payload = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()
    return digest[:8]


def load_summary_line(jsonl_path: Path) -> Dict[str, Any]:
    if not jsonl_path.exists():
        raise FileNotFoundError(f"JSONL path not found: {jsonl_path}")
    summary: Dict[str, Any] | None = None
    with jsonl_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict) and data.get("event") == "summary":
                summary = data
    if summary is None:
        raise RuntimeError(f"Summary not found in {jsonl_path}")
    return summary


def _seed_key(value: str) -> int | str:
    if value and value.isdigit():
        return int(value)
    return value


def _normalize_summary_row(row: Dict[str, str]) -> Dict[str, str]:
    normalized = {column: "" for column in SUMMARY_COLUMNS}
    for key, value in row.items():
        if key in normalized and value is not None:
            normalized[key] = value
    if not normalized.get("python_version") and row.get("py_version"):
        normalized["python_version"] = row["py_version"]
    return normalized


def read_summary(summary_path: Path) -> List[Dict[str, str]]:
    if not summary_path.exists():
        return []
    with summary_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            return []
        recognized = reader.fieldnames in (list(SUMMARY_COLUMNS), list(LEGACY_SUMMARY_COLUMNS))
        rows: List[Dict[str, str]] = []
        for raw in reader:
            row = dict(raw)
            if not recognized and not row.get("exp"):
                continue
            rows.append(_normalize_summary_row(row))
        return rows


def upsert_summary_row(rows: List[Dict[str, str]], row: Dict[str, str]) -> List[Dict[str, str]]:
    updated = False
    for existing in rows:
        if existing.get("exp") == row.get("exp") and existing.get("seed") == row.get("seed"):
            existing.update(row)
            updated = True
            break
    if not updated:
        rows.append(row)
    rows.sort(key=lambda item: (item.get("exp", ""), _seed_key(item.get("seed", ""))))
    return rows


def write_summary(summary_path: Path, rows: Iterable[Dict[str, str]]) -> None:
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(SUMMARY_COLUMNS))
        writer.writeheader()
        for row in rows:
            payload = {column: row.get(column, "") for column in SUMMARY_COLUMNS}
            writer.writerow(payload)


__all__ = [
    "SUMMARY_COLUMNS",
    "load_config",
    "make_exp_id",
    "load_summary_line",
    "read_summary",
    "upsert_summary_row",
    "write_summary",
]

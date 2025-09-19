#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import yaml


def load_config(path: str | os.PathLike[str]) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def decide(tag: str, requested_mode: str, allow_sensitive: bool) -> dict:
    tag_normalized = (tag or "benign").strip().lower()
    requested = (requested_mode or "SHIM").strip().upper()
    decision = {
        "requested_mode": requested,
        "tag": tag_normalized,
        "allowed": True,
        "effective_mode": requested,
        "reason": "",
    }
    if requested != "REAL":
        return decision
    if tag_normalized == "benign":
        return decision
    if tag_normalized == "sensitive" and not allow_sensitive:
        decision.update(
            {
                "allowed": False,
                "effective_mode": "SHIM",
                "reason": "policy: sensitive routed to SHIM (no override)",
            }
        )
        return decision
    if tag_normalized == "prohibited":
        decision.update(
            {
                "allowed": False,
                "effective_mode": "SHIM",
                "reason": "policy: prohibited content never sent to REAL",
            }
        )
        return decision
    return decision


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv
    if len(args) < 2:
        print(json.dumps({"error": "usage: policy_gate.py <CONFIG>"}))
        return 2

    cfg_path = Path(args[1]).expanduser().resolve()
    requested_mode = os.environ.get("MODE", "SHIM")
    allow_sensitive = os.environ.get("ALLOW_SENSITIVE", "0") == "1"

    cfg = load_config(cfg_path)
    tag = cfg.get("policy") or cfg.get("policy_tag") or "benign"

    decision = decide(tag, requested_mode, allow_sensitive)
    print(json.dumps(decision))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())

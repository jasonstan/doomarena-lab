#!/usr/bin/env python3
"""Apply regex verifiers to MVP demo rows and compute summary statistics."""

from __future__ import annotations

import argparse
import csv
import json
import pathlib
import re
from collections import defaultdict
from typing import Any

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - fallback if PyYAML absent
    yaml = None  # type: ignore


def _load_spec(path: pathlib.Path) -> dict[str, Any]:
    data = path.read_text(encoding="utf-8")
    if yaml is not None:
        loaded = yaml.safe_load(data)
        if not isinstance(loaded, dict):  # pragma: no cover - defensive
            raise ValueError("Spec must be a mapping")
        return loaded
    # Minimal fallback identical to translator
    import ast

    sanitized = []
    for line in data.splitlines():
        if "#" in line:
            line = line.split("#", 1)[0]
        sanitized.append(line)
    pseudo_yaml = "\n".join(sanitized)
    try:
        return ast.literal_eval(pseudo_yaml)
    except Exception as exc:  # pragma: no cover - fallback path
        raise ValueError("Unable to parse spec without PyYAML") from exc


def _compile_verifiers(spec: dict[str, Any]) -> dict[str, list[re.Pattern[str]]]:
    compiled: dict[str, list[re.Pattern[str]]] = {}
    for entry in spec.get("threats", []):
        attack_id = entry.get("attack_id")
        verifier = entry.get("verifier", {})
        if not attack_id or not isinstance(verifier, dict):
            continue
        if verifier.get("type") != "regex_any":
            continue
        patterns = verifier.get("patterns", [])
        compiled_patterns: list[re.Pattern[str]] = []
        for pattern in patterns:
            if not isinstance(pattern, str):
                continue
            flags = 0
            pattern_text = pattern
            if "(?i)" in pattern_text:
                flags |= re.IGNORECASE
                pattern_text = pattern_text.replace("(?i)", "")
            compiled_patterns.append(re.compile(pattern_text, flags))
        if compiled_patterns:
            compiled[str(attack_id)] = compiled_patterns
    return compiled


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify MVP demo rows against regex rules")
    parser.add_argument("--rows", required=True, type=pathlib.Path)
    parser.add_argument("--spec", required=True, type=pathlib.Path)
    parser.add_argument("--out", required=True, type=pathlib.Path)
    args = parser.parse_args()

    spec = _load_spec(args.spec)
    verifiers = _compile_verifiers(spec)

    rows_path = args.rows
    rows: list[dict[str, Any]] = []
    with rows_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            rows.append(row)

    attempts_by_attack = defaultdict(int)
    success_by_attack = defaultdict(int)

    for row in rows:
        attack_id = row.get("attack_id")
        output_text = row.get("output_text", "")
        success = False
        if isinstance(attack_id, str) and attack_id in verifiers and isinstance(output_text, str):
            for pattern in verifiers[attack_id]:
                if pattern.search(output_text):
                    success = True
                    break
        if row.get("error"):
            success = False
        row["success"] = bool(success)
        if isinstance(attack_id, str):
            attempts_by_attack[attack_id] += 1
            if success:
                success_by_attack[attack_id] += 1

    with rows_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    summary_rows: list[tuple[str, int, int, float]] = []
    for attack_id in sorted(attempts_by_attack):
        attempts = attempts_by_attack[attack_id]
        successes = success_by_attack[attack_id]
        asr = successes / attempts if attempts else 0.0
        summary_rows.append((attack_id, attempts, successes, asr))

    total_attempts = sum(attempts_by_attack.values())
    total_successes = sum(success_by_attack.values())
    overall_asr = total_successes / total_attempts if total_attempts else 0.0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["attack_id", "attempts", "successes", "asr"])
        for attack_id, attempts, successes, asr in summary_rows:
            writer.writerow([attack_id, attempts, successes, f"{asr:.4f}"])
        writer.writerow(["overall", total_attempts, total_successes, f"{overall_asr:.4f}"])


if __name__ == "__main__":
    main()

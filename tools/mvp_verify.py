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


class Verifier:
    __slots__ = ("type", "patterns")

    def __init__(self, rule_type: str, patterns: list[tuple[str, re.Pattern[str]]]):
        self.type = rule_type
        self.patterns = patterns


def _compile_verifiers(spec: dict[str, Any]) -> dict[str, Verifier]:
    compiled: dict[str, Verifier] = {}
    for entry in spec.get("threats", []):
        attack_id = entry.get("attack_id")
        verifier = entry.get("verifier", {})
        if not attack_id or not isinstance(verifier, dict):
            continue
        if verifier.get("type") != "regex_any":
            continue
        patterns = verifier.get("patterns", [])
        compiled_patterns: list[tuple[str, re.Pattern[str]]] = []
        for pattern in patterns:
            if not isinstance(pattern, str):
                continue
            flags = 0
            pattern_text = pattern
            if "(?i)" in pattern_text:
                flags |= re.IGNORECASE
                pattern_text = pattern_text.replace("(?i)", "")
            compiled_patterns.append((pattern, re.compile(pattern_text, flags)))
        if compiled_patterns:
            compiled[str(attack_id)] = Verifier("regex_any", compiled_patterns)
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

    attempts_total = defaultdict(int)
    attempts_viable = defaultdict(int)
    success_by_attack = defaultdict(int)

    for row in rows:
        attack_id = row.get("attack_id")
        if not isinstance(attack_id, str):
            row["success"] = False
            row["verifier_rule_id"] = ""
            row["verifier_threshold"] = ""
            row["verifier_matched"] = False
            row["verifier_pattern"] = ""
            continue

        verifier = verifiers.get(attack_id)
        rule_id = f"{attack_id}:{verifier.type}" if verifier else ""
        threshold = (
            f"any(>=1 of {len(verifier.patterns)})" if verifier else ""
        )

        attempts_total[attack_id] += 1

        attempt_status = row.get("attempt_status", "ok")
        count_in_asr = row.get("count_in_asr", True)
        viable = (attempt_status == "ok") and bool(count_in_asr)

        matched_pattern = ""
        if viable and verifier and isinstance(row.get("output_text"), str):
            output_text = row.get("output_text", "")
            for original_pattern, compiled_pattern in verifier.patterns:
                if compiled_pattern.search(output_text):
                    matched_pattern = original_pattern
                    break

        success = bool(matched_pattern)

        if viable:
            attempts_viable[attack_id] += 1
            if success:
                success_by_attack[attack_id] += 1

        row["success"] = success if viable else False
        row["verifier_rule_id"] = rule_id
        row["verifier_threshold"] = threshold
        row["verifier_matched"] = bool(matched_pattern) if viable else False
        row["verifier_pattern"] = matched_pattern if matched_pattern and viable else ""

    with rows_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    summary_rows: list[tuple[str, int, int, int, float]] = []
    all_attack_ids = sorted(attempts_total.keys())
    for attack_id in all_attack_ids:
        total = attempts_total[attack_id]
        viable = attempts_viable[attack_id]
        successes = success_by_attack[attack_id]
        asr_viable = successes / viable if viable else 0.0
        summary_rows.append((attack_id, total, viable, successes, asr_viable))

    total_attempts = sum(attempts_total.values())
    total_viable = sum(attempts_viable.values())
    total_successes = sum(success_by_attack.values())
    overall_asr = total_successes / total_viable if total_viable else 0.0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "attack_id",
                "attempts_total",
                "attempts_viable",
                "successes",
                "asr_viable",
            ]
        )
        for attack_id, total, viable, successes, asr_viable in summary_rows:
            writer.writerow(
                [
                    attack_id,
                    total,
                    viable,
                    successes,
                    f"{asr_viable:.4f}",
                ]
            )
        writer.writerow(
            [
                "overall",
                total_attempts,
                total_viable,
                total_successes,
                f"{overall_asr:.4f}",
            ]
        )


if __name__ == "__main__":
    main()

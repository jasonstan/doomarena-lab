#!/usr/bin/env python3
"""Translate NL threats into deterministic prompt cases for the MVP demo."""

from __future__ import annotations

import argparse
import json
import pathlib
import random
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
    # Minimal YAML subset loader for known structure
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Translate NL threats into prompt cases")
    parser.add_argument("--spec", required=True, type=pathlib.Path)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--out", required=True, type=pathlib.Path)
    args = parser.parse_args()

    spec = _load_spec(args.spec)
    threats = spec.get("threats", [])
    personas = spec.get("personas", [])
    if not isinstance(threats, list) or not isinstance(personas, list):
        raise ValueError("Spec must include list fields 'threats' and 'personas'")

    random.seed(args.seed)

    records: list[dict[str, str]] = []
    for threat in sorted(threats, key=lambda item: item.get("attack_id", "")):
        attack_id = threat.get("attack_id")
        template = threat.get("prompt_template")
        if not attack_id or not template:
            continue
        for persona in sorted(personas):
            prompt = template.format(persona=persona)
            records.append(
                {
                    "attack_id": str(attack_id),
                    "persona": str(persona),
                    "prompt": prompt,
                }
            )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()

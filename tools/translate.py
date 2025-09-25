#!/usr/bin/env python3
"""Translate a threat model specification into deterministic cases.

This tool reads ``specs/threat_model.yaml`` (or a provided spec path) and
materialises the declarative slice definitions into a ``cases.jsonl`` file.
Each JSONL record contains the fields that the end-to-end MVP expects when
running ``make mvp`` in CI:

``trial``
    Zero-based index of the emitted case.
``task``
    Identifier of the slice/task in the threat model.
``persona``
    Persona under which the case should be executed.
``amount``
    Requested amount for the scenario (if provided by the spec).
``input_case``
    Deterministic identifier composed from task + attack id.
``system`` / ``user``
    System and user messages to feed into the model.
``attack_id`` / ``attack_prompt``
    Original identifiers from the spec for traceability.

The implementation is intentionally lightweight so that CI can depend on it
without extra packages beyond PyYAML.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, List, Optional

import yaml


@dataclass(frozen=True)
class ThreatCase:
    """Representation of a single translated case."""

    trial: int
    task: str
    persona: str
    amount: Optional[int]
    input_case: str
    system: str
    user: str
    attack_id: str
    attack_prompt: str


def _coerce_amount(value: object) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        try:
            return int(float(text))
        except ValueError:
            raise ValueError(f"Amount value {value!r} is not numeric") from None


def _split_template(template: str) -> tuple[str, str]:
    """Return ``(system, user_template)`` derived from the input template.

    The spec uses a multi-line template where one line typically starts with
    ``User:`` to indicate the user message. Everything before that is treated as
    the system prompt. If no explicit ``User:`` prefix exists we treat the
    entire template as the user message and keep the system prompt empty.
    """

    lines = template.strip("\n").splitlines()
    system_lines: List[str] = []
    user_lines: List[str] = []
    user_section_started = False

    for raw_line in lines:
        if not user_section_started and raw_line.strip().lower().startswith("user:"):
            user_section_started = True
            user_lines.append(raw_line.split(":", 1)[1].lstrip())
            continue

        if user_section_started:
            user_lines.append(raw_line)
        else:
            system_lines.append(raw_line)

    if not user_lines:
        # Entire template is the user prompt.
        return "", template.strip()

    system_text = "\n".join(line for line in system_lines if line).strip()
    user_template = "\n".join(user_lines).strip()
    return system_text, user_template


def _format_template(template: str, *, persona: str, amount: Optional[int], **extra: str) -> str:
    # ``amount`` is optional; expose as an empty string when missing so that
    # ``{amount}`` substitutions do not fail for slices that omit it.
    formatted_amount = "" if amount is None else amount
    return template.format(persona=persona, amount=formatted_amount, **extra)


def iter_cases(spec: dict) -> Iterator[ThreatCase]:
    slices = spec.get("slices")
    if not isinstance(slices, list) or not slices:
        raise ValueError("Threat model must define a non-empty 'slices' list")

    trial_index = 0
    for slice_spec in slices:
        task = slice_spec.get("task")
        if not task:
            raise ValueError("Each slice requires a 'task' field")

        personas = slice_spec.get("personas") or ["default"]
        if not isinstance(personas, list) or not personas:
            raise ValueError(f"Slice {task!r} must define at least one persona")

        metadata = slice_spec.get("metadata") or {}
        input_template = metadata.get("input_template")
        if not input_template:
            raise ValueError(f"Slice {task!r} must define metadata.input_template")
        system_template, user_template = _split_template(str(input_template))

        amounts_raw = slice_spec.get("amounts")
        if amounts_raw:
            if not isinstance(amounts_raw, list):
                raise ValueError(f"Slice {task!r} amounts must be a list")
            amounts = [_coerce_amount(value) for value in amounts_raw]
        else:
            amounts = [None]

        cases = slice_spec.get("metadata", {}).get("cases") or slice_spec.get("cases")
        if not cases:
            raise ValueError(f"Slice {task!r} must include cases under metadata.cases")

        if not isinstance(cases, list):
            raise ValueError(f"Slice {task!r} cases must be a list")

        for persona in personas:
            for amount in amounts:
                for case in cases:
                    attack_id = case.get("attack_id")
                    if not attack_id:
                        raise ValueError(f"Slice {task!r} case is missing attack_id")
                    attack_prompt = case.get("attack_prompt", "")

                    system = _format_template(
                        system_template or "",
                        persona=str(persona),
                        amount=amount,
                        attack_prompt=attack_prompt,
                    )
                    user = _format_template(
                        user_template,
                        persona=str(persona),
                        amount=amount,
                        attack_prompt=attack_prompt,
                    )

                    yield ThreatCase(
                        trial=trial_index,
                        task=str(task),
                        persona=str(persona),
                        amount=amount,
                        input_case=f"{task}-{attack_id}",
                        system=system,
                        user=user,
                        attack_id=str(attack_id),
                        attack_prompt=str(attack_prompt),
                    )
                    trial_index += 1


def write_jsonl(cases: Iterable[ThreatCase], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as handle:
        for case in cases:
            handle.write(json.dumps(case.__dict__, ensure_ascii=False) + "\n")


def load_spec(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    data = yaml.safe_load(text) or {}
    if not isinstance(data, dict):
        raise ValueError("Threat model spec must decode to a mapping")
    version = data.get("version")
    if version not in {1, "1"}:
        raise ValueError("Unsupported threat model version")
    return data


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Translate threat model to cases.jsonl")
    parser.add_argument("--spec", "--input", default="specs/threat_model.yaml", help="Path to threat model YAML")
    parser.add_argument("--out", "--output", default="results/demo/cases.jsonl", help="Where to write cases JSONL")
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    spec_path = Path(args.spec)
    out_path = Path(args.out)
    try:
        spec = load_spec(spec_path)
        cases = list(iter_cases(spec))
        write_jsonl(cases, out_path)
    except Exception as exc:  # pragma: no cover - surfaced to caller
        print(f"translator error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised via CLI
    sys.exit(main())


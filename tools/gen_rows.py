"""Utility for generating large rows.jsonl files for streaming tests."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Iterator

REASON_CODES: tuple[str, ...] = (
    "policy_default_allow",
    "budget_exhausted",
    "safety_triggered",
    "manual_override",
)

POST_DECISIONS: tuple[str, ...] = ("allow", "warn", "deny")


def _isoformat(timestamp: datetime) -> str:
    """Return timestamp formatted with ``Z`` suffix."""
    return timestamp.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def iter_rows(count: int) -> Iterator[dict[str, object]]:
    """Yield deterministic row payloads that mimic real aggregator inputs."""

    base_timestamp = datetime(2024, 1, 1, tzinfo=timezone.utc)
    for index in range(count):
        success = index % 5 != 0
        reason_code = REASON_CODES[index % len(REASON_CODES)]
        post_decision = POST_DECISIONS[index % len(POST_DECISIONS)]
        latency_ms = 100.0 + float(index % 25)
        prompt_tokens = 128 + (index % 5)
        completion_tokens = 64 + (index % 7)
        total_tokens = prompt_tokens + completion_tokens
        row = {
            "exp": "smoke_exp_stream",
            "trial": index + 1,
            "seed": f"seed-{index % 16}",
            "model": "demo.large-smoke",
            "timestamp": _isoformat(base_timestamp + timedelta(seconds=index)),
            "success": success,
            "callable": True,
            "latency_ms": latency_ms,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cost_usd": round(0.0002 * (1 + (index % 4)), 6),
            "judge_rule_id": f"rule-{index % 8}",
            "pre_call_gate": {
                "decision": "allow" if success else "warn",
                "reason_code": reason_code,
                "policy_id": "policy.default",
            },
            "post_call_gate": {
                "decision": post_decision,
                "reason_code": reason_code,
                "policy_id": "policy.default",
            },
            "post_gate": {
                "decision": post_decision,
                "reason_code": reason_code,
                "rule_id": f"policy.rule.{index % 5}",
            },
            "pre_gate": {
                "decision": "allow" if success else "warn",
                "reason_code": reason_code,
                "rule_id": f"policy.rule.{index % 5}",
            },
        }
        yield row


def write_rows(path: Path, *, count: int) -> None:
    """Write ``count`` rows to ``path`` in JSON Lines format."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for payload in iter_rows(count):
            handle.write(json.dumps(payload, separators=(",", ":")))
            handle.write("\n")


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--n",
        type=int,
        default=100_000,
        help="Number of rows to generate (default: 100000)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Where to write rows.jsonl",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Iterable[str] | None = None) -> None:
    args = parse_args(argv)
    if args.n < 0:
        raise SystemExit("--n must be non-negative")
    write_rows(args.out, count=args.n)


if __name__ == "__main__":
    main()

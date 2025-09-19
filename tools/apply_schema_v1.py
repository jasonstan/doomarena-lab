#!/usr/bin/env python3
"""
Apply schema v1 to a results run directory:
  - Ensure summary.csv has a 'schema' column with value '1'
  - Write run.json with results/summary schema versions + metadata
"""
from __future__ import annotations
import csv
import json
import sys
import subprocess
from pathlib import Path
from datetime import datetime, timezone

SCHEMA_VERSION = "1"

def git_info() -> dict:
    def run(args):
        try:
            return subprocess.check_output(args, stderr=subprocess.DEVNULL).decode().strip()
        except Exception:
            return ""
    return {
        "sha": run(["git", "rev-parse", "--short", "HEAD"]),
        "branch": run(["git", "rev-parse", "--abbrev-ref", "HEAD"]),
    }

def ensure_schema_column(csv_path: Path) -> None:
    if not csv_path.exists():
        return
    # read all rows
    with csv_path.open(newline="") as f:
        rdr = csv.DictReader(f)
        rows = list(rdr)
        fieldnames = [h for h in (rdr.fieldnames or [])]
    # add 'schema' field if missing
    if "schema" not in [(h or "") for h in fieldnames]:
        fieldnames.append("schema")
        for r in rows:
            r["schema"] = SCHEMA_VERSION
    else:
        # set/overwrite to current version
        for r in rows:
            r["schema"] = SCHEMA_VERSION
    # write back
    tmp = csv_path.with_suffix(".tmp.csv")
    with tmp.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    tmp.replace(csv_path)

def write_run_json(run_dir: Path) -> None:
    run_json = run_dir / "run.json"

    existing: dict[str, object] = {}
    if run_json.exists():
        try:
            existing = json.loads(run_json.read_text(encoding="utf-8"))
        except Exception:
            existing = {}

    out = dict(existing)
    out.update(
        {
            "results_schema": SCHEMA_VERSION,
            "summary_schema": SCHEMA_VERSION,
            "run_id": run_dir.name,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "git": git_info(),
        }
    )

    run_json.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")

def main(argv):
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        print("usage: apply_schema_v1.py <RUN_DIR>")
        return 2
    run_dir = Path(argv[1]).resolve()
    ensure_schema_column(run_dir / "summary.csv")
    write_run_json(run_dir)
    print(f"Schema v1 applied in {run_dir}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

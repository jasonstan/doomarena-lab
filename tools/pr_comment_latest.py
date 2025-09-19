#!/usr/bin/env python3
import csv, os, sys
from pathlib import Path

results = Path("results/LATEST")
svg = results / "summary.svg"
csvp = results / "summary.csv"

if not results.exists() or not svg.exists() or not csvp.exists():
    print("No latest artifacts to comment with.")
    sys.exit(0)

# Read minimal summary: show each exp and ASR
rows = []
with csvp.open(newline="") as f:
    rdr = csv.DictReader(f)
    for r in rdr:
        exp = (r.get("exp") or r.get("experiment") or "").strip()
        asr = r.get("asr") or r.get("attack_success_rate") or ""
        rows.append((exp, asr))

# Build Markdown table (first 6 rows to keep short)
lines = ["| Experiment | ASR |", "|---|---|"]
for exp, asr in rows[:6]:
    lines.append(f"| `{exp}` | **{asr}** |")

md_table = "\n".join(lines)

# GitHub markdown to render artifact image via workflow upload URL:
# We'll attach the SVG path as a relative artifact link mention in the comment text.
# Consumers click through the artifacts; GitHub won't render the raw SVG inline from artifacts,
# so we include a small placeholder code block pointing to the file path.
body = f"""
### DoomArena-Lab PR smoke results

**Latest artifacts**: `results/LATEST/`

{md_table}

_Preview path_: `results/LATEST/summary.svg` (see **Artifacts** in this run)
"""
print(body.strip())

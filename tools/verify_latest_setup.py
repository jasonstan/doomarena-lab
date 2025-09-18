#!/usr/bin/env python3
import re
import sys
from pathlib import Path

repo = Path(__file__).resolve().parents[1]
readme = repo / "README.md"
makefile = repo / "Makefile"
tools = repo / "tools"

failures = []

# 1) README checks
if not readme.exists():
    failures.append("README.md is missing")
else:
    txt = readme.read_text(encoding="utf-8")
    if "make latest" not in txt:
        failures.append("README: missing 'make latest' mention")
    if "make open-artifacts" not in txt:
        failures.append("README: missing 'make open-artifacts' mention")

# 2) Tools exist
for p in ["latest_run.py", "open_artifacts.py"]:
    if not (tools / p).exists():
        failures.append(f"tools/{p} is missing")

# 3) Makefile checks
if not makefile.exists():
    failures.append("Makefile is missing")
else:
    mtxt = makefile.read_text(encoding="utf-8")
    if not re.search(r"^latest:\s*$", mtxt, re.M):
        failures.append("Makefile: missing 'latest:' target")
    if not re.search(r"^open-artifacts:\s*", mtxt, re.M):
        failures.append("Makefile: missing 'open-artifacts:' target")
    # report depends on latest (e.g., 'report: latest')
    if not re.search(r"^report:\s*latest\b", mtxt, re.M):
        failures.append("Makefile: 'report' does not depend on 'latest'")

if failures:
    print("VERIFICATION: FAIL")
    for f in failures:
        print(" -", f)
    sys.exit(1)
else:
    print("VERIFICATION: PASS")
    print(" - README mentions both targets")
    print(" - tools/latest_run.py & tools/open_artifacts.py present")
    print(" - Makefile has targets and 'report: latest' dependency")
    sys.exit(0)

#!/usr/bin/env python3
import re, sys
from pathlib import Path

repo = Path(__file__).resolve().parents[1]
readme = repo / "README.md"
makefile = repo / "Makefile"
tools = repo / "tools"

failures = []
debug = []

def normalize(s: str) -> str:
    # Map common unicode hyphens to ASCII and collapse whitespace
    s = (s.replace("\u2010","-")
           .replace("\u2011","-")
           .replace("\u2012","-")
           .replace("\u2013","-")
           .replace("\u2014","-")
           .replace("\u2015","-")
           .replace("\u2212","-")
           .replace("\xa0"," "))
    s = re.sub(r"[ \t]+", " ", s)
    return s

def grep_snippet(txt: str, pattern: str, lines=3):
    """Return a small snippet around the first match (for debug)."""
    m = re.search(pattern, txt, re.M | re.I)
    if not m:
        return "(no match)"
    start = txt.rfind("\n", 0, m.start())
    end = txt.find("\n", m.end())
    if start < 0: start = 0
    if end < 0: end = len(txt)
    return txt[start:end].strip()

# 1) README checks
if not readme.exists():
    failures.append("README.md is missing")
else:
    raw = readme.read_text(encoding="utf-8")
    txt = normalize(raw)

    # Accept any 'make  latest' with flexible whitespace
    patt_latest = r"make\s+latest"
    patt_open = r"make\s+open-artifacts"

    if not re.search(patt_latest, txt, re.I):
        failures.append("README: missing 'make latest' mention")
        debug.append("Snippet search latest: " + grep_snippet(txt, patt_latest))
    else:
        debug.append("Found 'make latest': " + grep_snippet(txt, patt_latest))

    if not re.search(patt_open, txt, re.I):
        failures.append("README: missing 'make open-artifacts' mention")
        debug.append("Snippet search open-artifacts: " + grep_snippet(txt, patt_open))
    else:
        debug.append("Found 'make open-artifacts': " + grep_snippet(txt, patt_open))

# 2) Tools exist
for p in ["latest_run.py", "open_artifacts.py"]:
    if not (tools / p).exists():
        failures.append(f"tools/{p} is missing")

# 3) Makefile checks
if not makefile.exists():
    failures.append("Makefile is missing")
else:
    mtxt_raw = makefile.read_text(encoding="utf-8")
    mtxt = normalize(mtxt_raw)
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
    if debug:
        print("\nDEBUG:")
        for d in debug:
            print(" *", d)
    sys.exit(1)
else:
    print("VERIFICATION: PASS")
    print(" - README mentions both targets")
    print(" - tools/latest_run.py & tools/open_artifacts.py present")
    print(" - Makefile has targets and 'report: latest' dependency")
    sys.exit(0)

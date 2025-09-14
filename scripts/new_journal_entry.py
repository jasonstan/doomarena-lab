#!/usr/bin/env python3
"""
Create/update a daily journal entry under docs/journal/YYYY-MM-DD.md
and refresh docs/journal/index.md (newest first).

Usage:
  python scripts/new_journal_entry.py
  DATE=2025-09-16 SUB="DA wire-up smoke" python scripts/new_journal_entry.py
  python scripts/new_journal_entry.py --date 2025-09-16 --subtitle "DA wire-up smoke"
"""
from __future__ import annotations
import argparse
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

try:
    from zoneinfo import ZoneInfo  # py>=3.9
    TZ = ZoneInfo("Asia/Yerevan")
except Exception:
    TZ = None  # fallback to system local time

ROOT = Path(__file__).resolve().parents[1]
JOURNAL_DIR = ROOT / "docs" / "journal"
INDEX_PATH = JOURNAL_DIR / "index.md"

INDEX_HEADER = "# Project Journal (index)"

ENTRY_TEMPLATE = """# {date}{subtitle_line}

## What shipped
- 

## Why it matters
- 

## Links (PRs, JSONLs)
- 

## Next
- 
"""

INDEX_LINE_RE = re.compile(r"^- \[(\d{4}-\d{2}-\d{2})\]\(\./\1\.md\)(?: — (.*))?$")

@dataclass
class EntryMeta:
    date: str
    subtitle: str = ""

def today_str() -> str:
    now = datetime.now(TZ) if TZ is not None else datetime.now()
    return now.strftime("%Y-%m-%d")

def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def read_index() -> Tuple[str, Dict[str, str]]:
    if not INDEX_PATH.exists():
        return INDEX_HEADER, {}
    text = INDEX_PATH.read_text(encoding="utf-8").splitlines()
    header = INDEX_HEADER
    mapping: Dict[str, str] = {}
    for line in text:
        if line.strip().startswith("#"):
            header = line.strip()
            continue
        m = INDEX_LINE_RE.match(line.strip())
        if m:
            d = m.group(1)
            sub = (m.group(2) or "").strip()
            mapping[d] = sub
    return header or INDEX_HEADER, mapping

def write_index(entries: List[EntryMeta]) -> None:
    entries_sorted = sorted(entries, key=lambda e: e.date, reverse=True)
    lines = [INDEX_HEADER, ""]
    for e in entries_sorted:
        suffix = f" — {e.subtitle}" if e.subtitle else ""
        lines.append(f"- [{e.date}](./{e.date}.md){suffix}")
    ensure_dir(JOURNAL_DIR)
    INDEX_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

def create_entry(meta: EntryMeta) -> Path:
    ensure_dir(JOURNAL_DIR)
    entry_path = JOURNAL_DIR / f"{meta.date}.md"
    if entry_path.exists():
        return entry_path
    subtitle_line = f" — {meta.subtitle}" if meta.subtitle else ""
    content = ENTRY_TEMPLATE.format(date=meta.date, subtitle_line=subtitle_line)
    entry_path.write_text(content, encoding="utf-8")
    return entry_path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="YYYY-MM-DD (defaults to today)")
    parser.add_argument("--subtitle", help="short tag for index line", default=None)
    args = parser.parse_args()

    date_str = args.date or os.getenv("DATE") or today_str()
    subtitle = (args.subtitle if args.subtitle is not None else os.getenv("SUB")) or ""

    from datetime import datetime as _dt
    try:
        _dt.strptime(date_str, "%Y-%m-%d")
    except ValueError as e:
        raise SystemExit(f"Invalid --date '{date_str}', expected YYYY-MM-DD") from e

    meta = EntryMeta(date=date_str, subtitle=subtitle.strip())
    path = create_entry(meta)

    header, mapping = read_index()
    if meta.subtitle or (meta.date not in mapping):
        mapping[meta.date] = meta.subtitle

    entries: List[EntryMeta] = []
    for md in JOURNAL_DIR.glob("*.md"):
        if md.name == "index.md":
            continue
        m = re.match(r"(\d{4}-\d{2}-\d{2})\.md$", md.name)
        if not m:
            continue
        d = m.group(1)
        entries.append(EntryMeta(date=d, subtitle=mapping.get(d, "")))
    write_index(entries)

    print(f"Journal entry: {path}")
    print(f"Index updated: {INDEX_PATH}")

if __name__ == "__main__":
    main()

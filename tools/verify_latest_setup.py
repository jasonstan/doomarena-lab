#!/usr/bin/env python3
"""Verify DoomArena latest-run wiring and optional CI pre-flight requirements."""

from __future__ import annotations

import argparse
import importlib
import os
import re
import sys
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]


def normalize(text: str) -> str:
    """Normalise unicode punctuation and collapse whitespace for regex searches."""

    replacements = {
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2015": "-",
        "\u2212": "-",
        "\xa0": " ",
    }
    for needle, repl in replacements.items():
        text = text.replace(needle, repl)
    return re.sub(r"[ \t]+", " ", text)


def grep_snippet(text: str, pattern: str) -> str:
    match = re.search(pattern, text, re.M | re.I)
    if not match:
        return "(no match)"
    start = text.rfind("\n", 0, match.start())
    end = text.find("\n", match.end())
    if start < 0:
        start = 0
    if end < 0:
        end = len(text)
    return text[start:end].strip()


def check_default_wiring() -> Tuple[List[str], List[str]]:
    failures: List[str] = []
    debug: List[str] = []

    readme = REPO_ROOT / "README.md"
    makefile = REPO_ROOT / "Makefile"
    tools_dir = REPO_ROOT / "tools"

    if not readme.exists():
        failures.append("README.md is missing")
    else:
        raw = readme.read_text(encoding="utf-8")
        txt = normalize(raw)
        patt_latest = r"make\s+latest"
        if not re.search(patt_latest, txt, re.I):
            failures.append("README: missing 'make latest' mention")
            debug.append("Snippet search latest: " + grep_snippet(txt, patt_latest))
        else:
            debug.append("Found 'make latest': " + grep_snippet(txt, patt_latest))

    if not (tools_dir / "latest_run.py").exists():
        failures.append("tools/latest_run.py is missing")

    if not makefile.exists():
        failures.append("Makefile is missing")
    else:
        mtxt_raw = makefile.read_text(encoding="utf-8")
        mtxt = normalize(mtxt_raw)
        if not re.search(r"^latest:\s*$", mtxt, re.M):
            failures.append("Makefile: missing 'latest:' target")
        if not re.search(r"^report:\s*.*\blatest\b", mtxt, re.M):
            failures.append("Makefile: 'report' does not depend on 'latest'")

    return failures, debug


def check_required_env(vars_to_check: Sequence[str]) -> List[str]:
    failures: List[str] = []
    for name in vars_to_check:
        if not name:
            continue
        if not os.environ.get(name):
            failures.append(
                f"Missing required environment variable {name}. Set it in repository secrets or the runner environment."
            )
    return failures


def check_required_imports(modules: Sequence[str]) -> List[str]:
    failures: List[str] = []
    for module in modules:
        if not module:
            continue
        try:
            importlib.import_module(module)
        except Exception as exc:  # pragma: no cover - defensive logging only
            failures.append(
                "Missing Python module '{mod}'. Install dependencies via requirements-ci.txt (e.g. run 'make install'). (import "
                "error: {err})".format(mod=module, err=exc)
            )
    return failures


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify latest-run wiring and optional CI pre-flight dependencies"
    )
    parser.add_argument(
        "--require-env",
        action="append",
        default=[],
        dest="require_env",
        help="Environment variable that must be set (may be used multiple times)",
    )
    parser.add_argument(
        "--require-import",
        action="append",
        default=[],
        dest="require_import",
        help="Python module that must import successfully (may be used multiple times)",
    )
    parser.add_argument(
        "--skip-default-checks",
        action="store_true",
        help="Skip README/Makefile verification and only run explicit checks",
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    failures: List[str] = []
    debug_messages: List[str] = []

    if not args.skip_default_checks:
        default_failures, default_debug = check_default_wiring()
        failures.extend(default_failures)
        debug_messages.extend(default_debug)

    failures.extend(check_required_env(args.require_env))
    failures.extend(check_required_imports(args.require_import))

    if failures:
        print("VERIFICATION: FAIL")
        for item in failures:
            print(" -", item)
        if debug_messages:
            print("\nDEBUG:")
            for entry in debug_messages:
                print(" *", entry)
        return 1

    print("VERIFICATION: PASS")
    if not args.skip_default_checks:
        print(" - README mentions 'make latest'")
        print(" - tools/latest_run.py present")
        print(" - Makefile has 'latest' target and 'report: latest' dependency")
    if args.require_env:
        joined = ", ".join(args.require_env)
        print(f" - Required environment variables present: {joined}")
    if args.require_import:
        joined = ", ".join(args.require_import)
        print(f" - Required Python modules importable: {joined}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

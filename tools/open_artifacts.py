#!/usr/bin/env python3
import platform, pathlib, subprocess, sys

def opener_cmd():
    s = platform.system().lower()
    if "darwin" in s: return ["open"]
    if "linux" in s: return ["xdg-open"]
    return None

def resolve_latest(base: pathlib.Path) -> pathlib.Path | None:
    link = base / "LATEST"
    pointer = base / "LATEST.path"
    if link.is_symlink():
        try: return link.resolve(strict=True)
        except FileNotFoundError: return None
    if link.exists() and link.is_dir():
        return link.resolve()
    if pointer.exists():
        t = pathlib.Path(pointer.read_text(encoding="utf-8").strip())
        return t if t.exists() else None
    return None

def main():
    results = pathlib.Path("results").resolve()
    run = resolve_latest(results)
    if not run:
        print("No latest artifacts found. Try: make demo && make report")
        return 1
    svg, csv = run / "summary.svg", run / "summary.csv"
    missing = [p for p in (svg, csv) if not p.exists()]
    if missing:
        print("Missing artifacts:", ", ".join(str(m) for m in missing))
        return 1
    cmd = opener_cmd()
    if cmd:
        try:
            subprocess.run(cmd + [str(svg)], check=False)
            subprocess.run(cmd + [str(csv)], check=False)
        except Exception:
            pass
    print(f"SVG: {svg}")
    print(f"CSV: {csv}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

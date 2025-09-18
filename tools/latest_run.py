#!/usr/bin/env python3
import sys, pathlib

def is_valid_run(d: pathlib.Path) -> bool:
    return (d / "summary.csv").exists() and (d / "summary.svg").exists()

def newest_run(results: pathlib.Path):
    if not results.exists():
        return None
    cands = [p for p in results.iterdir() if p.is_dir() and p.name != "LATEST"]
    cands = [p for p in cands if is_valid_run(p)]
    if not cands:
        return None
    cands.sort(key=lambda p: p.stat().st_mtime)
    return cands[-1]

def main():
    results = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "results").resolve()
    link = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else results / "LATEST")
    run = newest_run(results)
    if not run:
        print(f"No valid run found under {results} (need summary.csv and summary.svg).")
        return 1
    # Replace existing symlink/file (avoid removing a real dir)
    if link.exists() or link.is_symlink():
        try:
            if link.is_symlink() or link.is_file():
                link.unlink()
        except Exception:
            pass
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        link.symlink_to(run, target_is_directory=True)
        print(f"UPDATED: {link} -> {run}")
    except Exception as e:
        # Fallback pointer file if symlink not allowed
        pointer = link.parent / "LATEST.path"
        pointer.write_text(str(run), encoding="utf-8")
        print(f"Symlink failed ({e}); wrote {pointer} -> {run}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

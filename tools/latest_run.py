#!/usr/bin/env python3
import sys
import pathlib

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

def write_fallback_file(link: pathlib.Path, target: pathlib.Path):
    # If symlinks aren’t available, write a pointer file
    pointer = link.parent / "LATEST.path"
    pointer.write_text(str(target), encoding="utf-8")

def main():
    results = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "results").resolve()
    link = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else results / "LATEST")
    run = newest_run(results)
    if not run:
        print(f"No valid run found under {results} (need summary.csv and summary.svg).")
        print("Try: make demo && make report")
        sys.exit(1)
    # Clean any existing link/file
    link_exists = link.exists() or link.is_symlink()
    if link_exists:
        try:
            if link.is_symlink() or link.is_file():
                link.unlink()
            else:
                # Avoid deleting a real directory named LATEST
                raise RuntimeError(f"{link} exists and is not a symlink/file")
        except Exception as e:
            print(f"Warning: could not remove existing {link}: {e}")
    try:
        link.parent.mkdir(parents=True, exist_ok=True)
        # Try to create a symlink
        link.symlink_to(run, target_is_directory=True)
        print(f"UPDATED: {link} -> {run}")
    except Exception as e:
        # Fallback: write pointer file
        print(f"Symlink failed ({e}); writing LATEST.path instead.")
        write_fallback_file(link, run)
        print(f"UPDATED: {link.parent/'LATEST.path'} -> {run}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

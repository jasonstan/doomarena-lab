from pathlib import Path
import sys, json, csv
from typing import Optional, Tuple

# --- begin bootstrap so `from tools...` works without PYTHONPATH ---
here = Path(__file__).resolve()
repo_root = here.parent.parent  # <repo>/tools/.. => <repo>
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))
# --- end bootstrap ---


# === begin: robust input discovery ===
def _first_match(run_dir: Path, pattern: str) -> Path | None:
    try:
        for p in run_dir.glob(pattern):
            if p.is_file():
                return p
    except Exception:
        pass
    return None


def locate_inputs(run_dir: Path) -> tuple[Path | None, Path | None]:
    """
    Return (run_json_path, rows_jsonl_path), preferring top-level but
    falling back to first nested match. If both exist in different parents,
    prefer the pair that share a parent directory.
    """

    # Prefer top-level first
    top_run = run_dir / "run.json"
    top_rows = run_dir / "rows.jsonl"
    run_json = top_run if top_run.is_file() else _first_match(run_dir, "**/run.json")
    rows_jl = top_rows if top_rows.is_file() else _first_match(run_dir, "**/rows.jsonl")

    # If mismatched parents, try to co-locate next to rows.jsonl
    if run_json and rows_jl and run_json.parent != rows_jl.parent:
        coloc = rows_jl.parent / "run.json"
        if coloc.is_file():
            run_json = coloc
    return run_json, rows_jl
# === end: robust input discovery ===


def resolve_run_dir(path: Path) -> Path:
    """Resolve symlinks and fallback pointer files like results/LATEST.path."""

    resolved = path.resolve(strict=False)
    if resolved.exists():
        return resolved

    pointer = path.parent / f"{path.name}.path"
    if pointer.exists():
        target = Path(pointer.read_text(encoding="utf-8").strip())
        if target.exists():
            try:
                return target.resolve()
            except Exception:
                return target

    return resolved


def load_summary(run_dir: Path):
    p_json = run_dir / "summary_index.json"
    if p_json.exists():
        try:
            return "json", json.loads(p_json.read_text(encoding="utf-8"))
        except Exception:
            pass
    p_csv = run_dir / "summary.csv"
    if p_csv.exists():
        try:
            rows = list(csv.DictReader(p_csv.open(encoding="utf-8")))
            return "csv", {"csv_rows": rows}
        except Exception:
            pass
    return "none", {}


def _extract_from_run_json(data: dict, run_meta: dict) -> None:
    """Populate model/seed fields from run.json metadata when missing."""

    def _first_present(keys: Tuple[str, ...]) -> Optional[str]:
        for key in keys:
            parts = key.split(".")
            node: object = run_meta
            for part in parts:
                if isinstance(node, dict) and part in node:
                    node = node[part]
                else:
                    node = None
                    break
            if node not in (None, ""):
                return str(node)
        return None

    # Only override when the current value is missing or "unknown".
    model = _first_present((
        "model",
        "config.model",
        "real.model",
        "meta.model",
    ))
    current_model = str(data.get("model") or "").strip().lower()
    if model and (not current_model or current_model == "unknown"):
        data["model"] = model

    seed = _first_present((
        "seed",
        "meta.seed",
        "config.seed",
        "params.seed",
    ))
    current_seed = str(data.get("seed") or "").strip()
    if seed and (not current_seed or current_seed == "unknown"):
        data["seed"] = seed

def _degraded_html(run_dir: Path, err: Exception | None = None) -> str:
    msg = f"{type(err).__name__}: {err}" if err else "no data"
    return f"""<!doctype html><meta charset="utf-8">
<title>DoomArena-Lab Report (degraded)</title>
<h1>Report (degraded)</h1>
<p>Could not render full report ({msg}).</p>
<p>Artifacts are in <code>{run_dir.name}</code>.</p>
<ul>
  <li><code>summary.csv</code></li>
  <li><code>summary.svg</code></li>
  <li><code>rows.jsonl</code></li>
  <li><code>run.json</code></li>
</ul>
"""

def main():
    if len(sys.argv) <= 1:
        print("ERROR: mk_report: missing run_dir", file=sys.stderr)
        sys.exit(2)

    requested = Path(sys.argv[1])
    run_dir = resolve_run_dir(requested)
    if not run_dir.exists():
        print(f"ERROR: mk_report: run_dir does not exist: {requested}", file=sys.stderr)
        sys.exit(2)

    out_path = run_dir / "index.html"

    mode, data = load_summary(run_dir)

    run_json_path, rows_path = locate_inputs(run_dir)

    run_meta: dict = {}
    model = seed = "unknown"
    if run_json_path:
        try:
            run_meta = json.loads(run_json_path.read_text(encoding="utf-8"))
            model = run_meta.get("model", run_meta.get("config", {}).get("model", "unknown"))
            seed = run_meta.get("seed", run_meta.get("config", {}).get("seed", "unknown"))
        except Exception:
            run_meta = {}

    rows_preview: list[dict] = []
    if rows_path:
        try:
            with rows_path.open("r", encoding="utf-8") as fh:
                for i, line in enumerate(fh):
                    if i >= 5000:
                        break
                    try:
                        rows_preview.append(json.loads(line))
                    except Exception:
                        continue
        except Exception:
            rows_preview = []

    if run_meta:
        if mode != "json":
            # Keep original structure for csv/none modes while surfacing metadata.
            data = dict(data)
            if mode == "csv":
                data.setdefault("csv_rows", [])
        _extract_from_run_json(data, run_meta)
    else:
        # Populate best-effort metadata even if run.json failed to parse.
        if mode == "json":
            data = dict(data)
            data.setdefault("model", model)
            data.setdefault("seed", seed)
        elif mode == "csv":
            data = dict(data)
            rows = list(data.get("csv_rows", []))
            if rows:
                rows[0].setdefault("model", model)
                rows[0].setdefault("seed", seed)
            data["csv_rows"] = rows


    # Import template renderer safely
    try:
        from tools.report import html_report  # type: ignore
    except Exception as e:
        out_path.write_text(_degraded_html(run_dir, e), encoding="utf-8")
        print(f"Wrote {out_path} (degraded: import error)")
        return
    render_html = html_report.render_html  # type: ignore[attr-defined]

    if rows_path or rows_preview:
        fallback_rows = rows_path

        def _read_rows_jsonl_override(target_dir: Path, limit: int = 50):
            if rows_preview:
                cap = min(limit, len(rows_preview))
                return rows_preview[:cap]

            candidates: list[Path | None] = []
            default = target_dir / "rows.jsonl"
            if fallback_rows and fallback_rows != default:
                candidates.append(fallback_rows)
            candidates.append(default)

            for candidate in candidates:
                if not candidate or not candidate.exists():
                    continue
                out = []
                try:
                    with candidate.open(encoding="utf-8") as f:
                        for i, line in enumerate(f):
                            if i >= limit or i >= 5000:
                                break
                            try:
                                obj = json.loads(line)
                            except Exception:
                                continue
                            out.append(obj)
                except Exception:
                    continue
                if out:
                    return out
            return []

        html_report._read_rows_jsonl = _read_rows_jsonl_override  # type: ignore[attr-defined]

    # Attempt full render; fall back to degraded on any error
    degraded = False
    try:
        html = render_html(run_dir, data, mode=mode)
    except Exception as e:
        html = _degraded_html(run_dir, e)
        degraded = True

    out_path.write_text(html, encoding="utf-8")
    if degraded:
        print(f"Wrote {out_path} (degraded)")
    else:
        print(f"Wrote {out_path}")

if __name__ == "__main__":
    main()
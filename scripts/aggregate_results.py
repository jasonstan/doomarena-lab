from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

SUMMARY_COLUMNS: Tuple[str, ...] = (
    "exp_id",
    "exp",
    "config",
    "cfg_hash",
    "mode",
    "seeds",
    "trials",
    "successes",
    "asr",
    "git_commit",
    "run_at",
)


def read_jsonl(path: Path) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    header: Dict[str, Any] | None = None
    summary: Dict[str, Any] | None = None
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            event = payload.get("event")
            if event == "header" and header is None:
                header = payload
            elif event == "summary":
                summary = payload
    if header is None:
        raise RuntimeError(f"Missing header in {path}")
    if summary is None:
        raise RuntimeError(f"Missing summary in {path}")
    return header, summary


def _normalise_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _normalise_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _collect_seeds(header: Dict[str, Any]) -> str:
    seen: set[str] = set()
    ordered: List[str] = []

    def _add(item: Any) -> None:
        text = _stringify(item).strip()
        if not text:
            return
        if text in seen:
            return
        seen.add(text)
        ordered.append(text)

    if "seed" in header:
        _add(header.get("seed"))

    seeds_value = header.get("seeds")
    if isinstance(seeds_value, (list, tuple)):
        for item in seeds_value:
            _add(item)
    elif isinstance(seeds_value, str):
        for chunk in seeds_value.split(","):
            _add(chunk)
    elif seeds_value is not None:
        _add(seeds_value)

    return ",".join(ordered)


def _load_meta(path: Path) -> Dict[str, Any] | None:
    candidates = [
        path.with_suffix(".meta.json"),
        path.parent / "meta.json",
    ]
    for candidate in candidates:
        if not candidate.exists():
            continue
        try:
            with candidate.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict):
            return data
    return None


def _stringify_seeds(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        parts: List[str] = []
        for item in value:
            text = _stringify(item).strip()
            if text and text not in parts:
                parts.append(text)
        return ",".join(parts)
    if value is None:
        return ""
    return _stringify(value)


def build_row(path: Path, header: Dict[str, Any], summary: Dict[str, Any]) -> Dict[str, str]:
    meta = _load_meta(path)

    exp_id = _stringify(header.get("exp_id"))
    if meta and meta.get("exp_id"):
        exp_id = _stringify(meta.get("exp_id"))

    exp = _stringify(header.get("exp"))
    config = _stringify(header.get("config"))
    cfg_hash_value = _stringify(header.get("cfg_hash"))

    mode = _stringify(header.get("mode"))
    if meta and meta.get("mode"):
        mode = _stringify(meta.get("mode"))

    git_commit = _stringify(header.get("git_commit"))
    if not git_commit and meta and meta.get("git_commit"):
        git_commit = _stringify(meta.get("git_commit"))
    elif not git_commit and meta and meta.get("git_sha"):
        git_commit = _stringify(meta.get("git_sha"))

    run_at = _stringify(header.get("run_at"))
    if meta and meta.get("timestamp"):
        run_at = _stringify(meta.get("timestamp"))

    seeds = _collect_seeds(header)
    if meta and meta.get("seeds") is not None:
        seeds = _stringify_seeds(meta.get("seeds"))

    trials = _normalise_int(summary.get("trials"))
    if meta and meta.get("trials") is not None:
        try:
            trials = int(meta.get("trials"))
        except (TypeError, ValueError):
            pass
    successes = _normalise_int(summary.get("successes"))
    if trials > 0 and successes > trials:
        successes = trials
    asr_value = summary.get("asr")
    if asr_value is None and trials:
        asr_value = successes / trials
    asr = _normalise_float(asr_value)
    if asr < 0.0:
        asr = 0.0
    elif asr > 1.0:
        asr = 1.0

    row = {
        "exp_id": exp_id,
        "exp": exp,
        "config": config,
        "cfg_hash": cfg_hash_value,
        "mode": mode,
        "seeds": seeds,
        "trials": str(trials),
        "successes": str(successes),
        "asr": f"{asr:.6f}",
        "git_commit": git_commit,
        "run_at": run_at,
    }
    return row


def read_existing(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != list(SUMMARY_COLUMNS):
            return []
        return [dict(row) for row in reader]


def merge_rows(existing: List[Dict[str, str]], new_rows: Iterable[Dict[str, str]]) -> List[Dict[str, str]]:
    combined = list(existing)
    seen_keys = {
        (row.get("exp_id", ""), row.get("run_at", ""))
        for row in combined
    }
    for row in new_rows:
        key = (row.get("exp_id", ""), row.get("run_at", ""))
        if key in seen_keys:
            continue
        combined.append(row)
        seen_keys.add(key)
    combined.sort(key=lambda item: item.get("run_at", ""))
    return combined


def write_summary(path: Path, rows: Iterable[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(SUMMARY_COLUMNS))
        writer.writeheader()
        for row in rows:
            payload = {column: row.get(column, "") for column in SUMMARY_COLUMNS}
            writer.writerow(payload)


def write_summary_md(base_dir: Path, rows: List[Dict[str, str]]) -> None:
    md_path = base_dir / "summary.md"
    md_path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        md_path.write_text("No results available.\n", encoding="utf-8")
        return

    recent = sorted(rows, key=lambda item: item.get("run_at", ""), reverse=True)[:5]
    lines = [
        "| exp | seeds | mode | ASR | trials | successes | git | run_at |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in recent:
        try:
            asr_display = f"{float(row.get('asr', 0.0)):.2f}"
        except (TypeError, ValueError):
            asr_display = _stringify(row.get("asr"))
        successes = row.get("successes", "")
        trials = row.get("trials", "")
        if asr_display and successes and trials:
            asr_display = f"{asr_display} ({successes}/{trials})"
        git_commit = row.get("git_commit", "")[:8]
        lines.append(
            "| {exp} | {seeds} | {mode} | {asr} | {trials} | {successes} | {git} | {run_at} |".format(
                exp=row.get("exp", ""),
                seeds=row.get("seeds", ""),
                mode=row.get("mode", ""),
                asr=asr_display,
                trials=trials,
                successes=successes,
                git=git_commit,
                run_at=row.get("run_at", ""),
            )
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    base_dir = Path("results")
    base_dir.mkdir(parents=True, exist_ok=True)
    summary_path = base_dir / "summary.csv"

    jsonl_files = sorted(base_dir.rglob("*.jsonl"))
    new_rows: List[Dict[str, str]] = []
    for path in jsonl_files:
        try:
            header, summary = read_jsonl(path)
        except RuntimeError as exc:
            print(f"Skipping {path}: {exc}")
            continue
        try:
            row = build_row(path, header, summary)
        except Exception as exc:  # pragma: no cover - defensive fallback
            print(f"Failed to process {path}: {exc}")
            continue
        new_rows.append(row)

    existing_rows = read_existing(summary_path)
    combined_rows = merge_rows(existing_rows, new_rows)

    write_summary(summary_path, combined_rows)
    write_summary_md(base_dir, combined_rows)


if __name__ == "__main__":
    main()

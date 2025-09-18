from __future__ import annotations

import csv
import json
import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

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


@dataclass
class ExperimentSummary:
    name: str
    trials: int
    weighted_successes: float
    successes: Optional[int]

    @property
    def asr(self) -> float:
        if self.trials <= 0:
            return 0.0
        return self.weighted_successes / float(self.trials)

    @property
    def asr_percent(self) -> float:
        return self.asr * 100.0


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


def _parse_optional_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    text = _stringify(value).strip()
    if not text:
        return None
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _parse_optional_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    text = _stringify(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


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


def _clamp(value: float, minimum: float, maximum: float) -> float:
    if value < minimum:
        return minimum
    if value > maximum:
        return maximum
    return value


def _parse_iso_timestamp(value: str) -> Optional[datetime]:
    text = _stringify(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _dedupe_preserve_order(values: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    ordered: List[str] = []
    for value in values:
        text = _stringify(value).strip()
        if not text:
            continue
        if text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return ordered


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


def _collect_seed_tokens(rows: Iterable[Dict[str, str]]) -> List[str]:
    seen: set[str] = set()
    ordered: List[str] = []
    for row in rows:
        seeds_value = row.get("seeds")
        if seeds_value is None:
            continue
        raw = _stringify(seeds_value).replace(";", ",")
        if not raw:
            continue
        for chunk in raw.split(","):
            token = chunk.strip()
            if not token:
                continue
            if token in seen:
                continue
            seen.add(token)
            ordered.append(token)
    return ordered


def summarise_experiments(rows: Iterable[Dict[str, str]]) -> List[ExperimentSummary]:
    aggregates: Dict[str, Dict[str, Any]] = {}

    for row in rows:
        exp_name = _stringify(row.get("exp"))
        exp = exp_name.strip()
        if not exp:
            continue

        trials_value = _parse_optional_int(row.get("trials"))
        if trials_value is None or trials_value <= 0:
            continue

        successes_value = _parse_optional_int(row.get("successes"))
        asr_value = _parse_optional_float(row.get("asr"))

        if successes_value is None and asr_value is None:
            continue

        bucket = aggregates.setdefault(
            exp,
            {
                "trials": 0,
                "weighted_successes": 0.0,
                "successes": 0,
                "has_exact_successes": True,
            },
        )

        bucket["trials"] = int(bucket["trials"]) + int(trials_value)

        if successes_value is not None:
            successes_clamped = max(0, min(int(successes_value), int(trials_value)))
            bucket["weighted_successes"] = float(bucket["weighted_successes"]) + float(successes_clamped)
            bucket["successes"] = int(bucket["successes"]) + successes_clamped
        else:
            asr_clamped = _clamp(asr_value or 0.0, 0.0, 1.0)
            bucket["weighted_successes"] = float(bucket["weighted_successes"]) + (asr_clamped * float(trials_value))
            bucket["has_exact_successes"] = False

    summaries: List[ExperimentSummary] = []
    for exp, payload in aggregates.items():
        trials_total = int(payload["trials"])
        weighted_successes = float(payload["weighted_successes"])
        has_exact_successes = bool(payload.get("has_exact_successes", False))
        if not has_exact_successes:
            successes_total: Optional[int] = None
        else:
            successes_total = int(payload.get("successes", 0))
        summaries.append(
            ExperimentSummary(
                name=exp,
                trials=trials_total,
                weighted_successes=weighted_successes,
                successes=successes_total,
            )
        )

    summaries.sort(key=lambda item: (-item.asr, item.name))
    return summaries


def _compute_overall_asr(experiments: Iterable[ExperimentSummary]) -> Optional[float]:
    total_trials = 0
    weighted = 0.0
    for item in experiments:
        total_trials += item.trials
        weighted += item.weighted_successes
    if total_trials <= 0:
        return None
    return (weighted / float(total_trials)) * 100.0


def _resolve_timestamp(rows: Iterable[Dict[str, str]]) -> str:
    latest: Optional[datetime] = None
    for row in rows:
        candidate = _parse_iso_timestamp(row.get("run_at", ""))
        if candidate is None:
            continue
        if latest is None or candidate > latest:
            latest = candidate
    if latest is None:
        latest = datetime.now(timezone.utc)
    return latest.astimezone().isoformat(timespec="seconds")


def _collect_modes(rows: Iterable[Dict[str, str]]) -> List[str]:
    return _dedupe_preserve_order(row.get("mode", "") for row in rows)


def _collect_git_commits(rows: Iterable[Dict[str, str]]) -> List[str]:
    return _dedupe_preserve_order(row.get("git_commit", "") for row in rows)


def _collect_experiments(rows: Iterable[Dict[str, str]]) -> List[str]:
    return _dedupe_preserve_order(row.get("exp", "") for row in rows)


def write_run_notes(base_dir: Path, rows: List[Dict[str, str]]) -> None:
    notes_path = base_dir / "notes.md"
    notes_path.parent.mkdir(parents=True, exist_ok=True)

    experiments = summarise_experiments(rows)
    timestamp_text = _resolve_timestamp(rows)
    seed_tokens = _collect_seed_tokens(rows)
    mode_tokens = _collect_modes(rows)
    git_commits = _collect_git_commits(rows)
    experiment_names = [item.name for item in experiments]
    if not experiment_names:
        experiment_names = _collect_experiments(rows)

    exp_summary = ", ".join(experiment_names) if experiment_names else "n/a"
    mode_summary = ", ".join(mode_tokens) if mode_tokens else "n/a"
    seed_summary = ", ".join(seed_tokens) if seed_tokens else "n/a"

    run_dir_text = base_dir.resolve().as_posix()
    git_commit = git_commits[0] if git_commits else ""
    git_commit_short = git_commit[:8] if git_commit else "n/a"

    total_trials = sum(item.trials for item in experiments)
    overall_asr = _compute_overall_asr(experiments)

    run_id = base_dir.name or run_dir_text
    header_exp = exp_summary if exp_summary != "n/a" else "<unknown>"
    header_mode = mode_summary if mode_summary != "n/a" else "n/a"

    lines: List[str] = []
    lines.append(f"# Experiment Notes – {header_exp} (mode={header_mode}) – {run_id}")
    lines.append("")
    if experiments:
        lines.append(
            "This run evaluated {count} experiment(s) across {trials} trials "
            "using mode(s) {modes} with seeds {seeds}.".format(
                count=len(experiments),
                trials=total_trials,
                modes=mode_summary,
                seeds=seed_summary,
            )
        )
    else:
        lines.append("No experiment results were found for this run.")
    lines.append("")

    lines.append("## Run metadata")
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("| --- | --- |")
    lines.append(f"| Timestamp | {timestamp_text} |")
    lines.append(f"| EXP | {exp_summary} |")
    lines.append(f"| MODE | {mode_summary} |")
    lines.append(f"| TRIALS | {total_trials} |")
    lines.append(f"| SEEDS | {seed_summary} |")
    lines.append(f"| RUN_DIR | {run_dir_text} |")
    lines.append(f"| GIT_COMMIT | {git_commit_short} |")
    lines.append("")

    if experiments:
        lines.append("## Results")
        lines.append("")
        lines.append("| Experiment | Trials | Successes | Trial-weighted ASR % |")
        lines.append("| --- | ---: | ---: | ---: |")
        for item in experiments:
            successes_display = str(item.successes) if item.successes is not None else "–"
            lines.append(
                "| {name} | {trials} | {successes} | {asr:.2f} |".format(
                    name=item.name,
                    trials=item.trials,
                    successes=successes_display,
                    asr=item.asr_percent,
                )
            )
        lines.append("")
    else:
        lines.append("## Results")
        lines.append("")
        lines.append("No aggregated results were available.")
        lines.append("")

    if overall_asr is None:
        overall_text = "n/a"
    else:
        overall_text = f"{overall_asr:.2f}%"
    lines.append(f"**Overall trial-weighted ASR:** {overall_text}")
    lines.append("")

    summary_csv = base_dir / "summary.csv"
    summary_svg = base_dir / "summary.svg"
    summary_png = base_dir / "summary.png"

    lines.append("## Artifacts")
    lines.append("")
    if summary_csv.exists():
        lines.append(f"- [summary.csv]({summary_csv.name})")
    else:
        lines.append("- summary.csv (missing)")
    if summary_svg.exists():
        lines.append(f"- [summary.svg]({summary_svg.name})")
    if summary_png.exists():
        lines.append(f"- [summary.png]({summary_png.name})")

    jsonl_paths = sorted(base_dir.rglob("*.jsonl"))
    if jsonl_paths:
        lines.append("- Per-seed logs:")
        for path in jsonl_paths:
            try:
                rel = path.relative_to(base_dir)
            except ValueError:
                rel = path
            rel_text = rel.as_posix()
            lines.append(f"  - [{rel_text}]({rel_text})")
    else:
        lines.append("- No per-seed logs were found.")

    chart_path: Optional[Path] = None
    if summary_svg.exists():
        chart_path = summary_svg
    elif summary_png.exists():
        chart_path = summary_png

    if chart_path is not None:
        lines.append("")
        lines.append(f"![Trial-weighted ASR chart]({chart_path.name})")

    lines.append("")
    notes_path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate DoomArena run outputs")
    parser.add_argument(
        "--outdir",
        default="results",
        help="Directory to scan for jsonl files and write summaries",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    base_dir = Path(args.outdir).expanduser()
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
    write_run_notes(base_dir, combined_rows)


if __name__ == "__main__":
    main()

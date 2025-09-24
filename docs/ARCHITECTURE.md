# DoomArena-Lab Architecture (builder view)

## Purpose
Decision-ready demos & guardrails for agent teams. Fast local runs, artifact-first CI.

## Data flow
```
configs/*/run.yaml ──▶ scripts/xsweep.py ──▶ results/<RUN_DIR>/
                             │
                             ├─ per-seed traces (*.jsonl) [optional]
                             ├─ summary.csv  (trial-weighted, schema=1)
                             ├─ summary.svg  (grouped bars)
                             ├─ run.json     (results_schema/summary_schema=1, git, timestamps)
                             └─ notes.md     (auto notes, optional)
                                     │
                                     ▼
make report ──▶ results/LATEST/ (mirror) + index.html (mini report)
                              ▲
                              └─ tools/latest_run.py picks newest valid run
```

## Contracts (keep stable)
- **summary.csv**: must include `exp`, `trials`, `successes`, `asr` (trial-weighted preferred); `schema` column set to `"1"`.
- **run.json**: includes `results_schema` and `summary_schema` (currently `"1"`), `run_id`, UTC timestamp, `git.sha`, `git.branch`.
- **LATEST**: symlink/marker to most recent run with valid `summary.csv` & `summary.svg`.

## CLI & orchestration
- `make demo` — quick SHIM runs to populate artifacts.
- `make xsweep CONFIG=...` — configurable sweep.
- `make report` — applies schema v1, builds HTML report, refreshes LATEST.
- `STREAM=1 make ...` — forwards `--stream` to the aggregator to process `rows.jsonl`
  line-by-line (same outputs, also records `malformed_rows` into `run.json`).
- `make latest`, `make open-artifacts` — convenience for inspection.
- CI: **smoke** (tiny SHIM sweep, uploads artifacts) + PR comment with schema + thresholds table.

## Thresholds (governance)
- `thresholds.yaml` supports `min_trials`, `max_asr`, `min_asr`. CI posts PASS/WARN/FAIL (warn-only default).

## Tech shape (keep it light)
- `scripts/_lib.py` centralizes CSV reading, weighting, git/time helpers.
- Thin scripts in `scripts/`; Makefile is the user interface.
- No heavy deps; pandas used only where helpful.

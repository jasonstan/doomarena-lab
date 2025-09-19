# DoomArena-Lab

_Demo-first companion to ServiceNow/DoomArena. Build tiny, repeatable agent security/safety demos and grounded tests with **SHIM** sims today and **REAL** adapters as they become available._

## Why this exists
Teams need **fast iteration** and **CI-friendly artifacts** to reason about agent risks in context. DoomArena-Lab gives you:
- **Modes**: **SHIM** (simulation adapters) now; **REAL** (upstream DoomArena adapters) when available, with SHIM fallback.
- **Make UX**: `make demo`, `make xsweep CONFIG=...`, `make report`, `make latest`, `make open-artifacts`.
- **Artifacts**: Timestamped run dirs under `results/<RUN_DIR>/` with `summary.csv`, `summary.svg`, and (when produced) per-seed JSONL traces.
- **Metrics/plots**: **Trial-weighted** micro-average ASR in a grouped-bar chart (via a tiny shared helper in `scripts/_lib.py`).

## Quick Start
```bash
# 1) Run a tiny SHIM sweep
make demo

# 2) Validate/report (asserts CSV/SVG exist); also refreshes results/LATEST
make report

# 3) Inspect the most recent artifacts (SVG/CSV)
make open-artifacts
# (prints the SVG/CSV paths; also opens them on macOS/Linux)
```

Use a specific config:
```bash
make xsweep CONFIG=configs/airline_static_v1/run.yaml
```

### Latest Results (auto)
The newest successful run is symlinked to `results/LATEST` (created/updated by `make report`).

![Latest results](results/LATEST/summary.svg)

If you see a broken image, run:
```bash
make demo && make report
```

## Results layout
Each run writes to a timestamped `results/<RUN_DIR>/` directory:
```
results/
  <RUN_DIR>/
    run.json
    summary.csv
    summary.svg
    ...seed_*.jsonl (optional per-seed traces)
```

**Schemas**: each run writes a `run.json` declaring `results_schema` / `summary_schema` (currently `"1"`), and `summary.csv` includes a `schema` column. Bump when columns or semantics change.
**Thresholds (optional):** declare guardrails in `thresholds.yaml` (`min_trials`, `max_asr`, `min_asr`). CI posts a PASS/WARN/FAIL table on each PR (warn-only by default). Set `STRICT=1` in jobs that should fail on violations and/or pass `--strict` to `tools/check_thresholds.py`.

**`summary.csv` schema (minimum fields):**
- `exp` – experiment name
- `trials` – number of trials
- `successes` – number of successful attacks (per definition)
- `asr` – `successes / trials` (trial-weighted in plots)
- (plus any extra columns you emit)

**`summary.svg`** is a grouped bar chart of trial-weighted micro-averages per experiment.

## Modes
- **SHIM** — simulation adapters for quick, deterministic demos.
- **REAL** — upstream DoomArena adapters when available. The lab falls back to SHIM if REAL is not present.

## Make targets (TL;DR)
- `make help` — list common targets & docs.
- `make demo` — tiny SHIM sweep to produce a minimal `results/<RUN_DIR>/`.
- `make xsweep CONFIG=...` — run a configurable sweep.
## Make targets (TL;DR)
- `make help` — list common targets & docs.
- `make demo` — tiny SHIM sweep to produce a minimal `results/<RUN_DIR>/`.
- `make xsweep CONFIG=...` — run a configurable sweep.
- `make report` — asserts `summary.csv` & `summary.svg`; updates `results/LATEST`.
- `make latest` — refreshes `results/LATEST` to the newest run with `summary.csv` & `summary.svg`.
- `make open-artifacts` — prints paths to `results/LATEST/summary.svg` and `summary.csv` (safe in CI). Add `--open` locally to launch files: `python tools/open_artifacts.py --open`.

### Testing
- ✅ `make test-unit` — runs fast unit tests inside `.venv`
- ✅ `make test` — runs all tests inside `.venv`
- ✅ `make demo` — auto-installs deps (`pyyaml`, `pandas`, `matplotlib`, etc.)
- ✅ `make report`
> All targets ensure a local `.venv` is created and dependencies are installed.

## CI
The smoke workflow runs a tiny SHIM sweep and publishes artifacts. It also updates `results/LATEST` for quick inspection in PRs.

## Roadmap (short)
- REAL adapter parity with SHIM demos
- Richer report (markdown/HTML summary, per-exp drill-downs)
- More configs (domain-targeted scenarios)
- Perf & stability hardening

## Contributing
PRs welcome. Keep demos fast and artifacts reproducible. Aim for small, reviewable changes.


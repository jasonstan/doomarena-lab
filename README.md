# DoomArena-Lab

_DoomArena-Lab is a small, e2e-oriented companion to ServiceNow/DoomArena. It helps teams build **tiny, repeatable demos and grounded tests** with **SHIM** sims today and a clear path to **REAL** adapters (first MVP: one cloud model)._

## What’s new (MVP progress)
- **REAL risky slice now writes rows** → `results/<RUN_ID>/tau_risky_real/rows.jsonl` + `run.json`
- **Aggregation works end-to-end** → `results/LATEST/summary.csv`, `summary.svg`, `index.html`
- **Basic governance hooks** → pre/post gates recorded in rows and audited in `run.json`
- **CI workflows**
  - `run-demo`: local logic smoke; uploads artifacts  
  - `run-real-mvp`: Groq model, manual dispatch with inputs (model, trials, seed)

## Quickstart
```bash
# 1) Set provider secret
export GROQ_API_KEY=...

# 2) Run the REAL slice locally (cheap default)
python -m scripts.experiments.tau_risky_real --trials 6 --seed 42

# 3) Build report
make report   # or: python -m scripts.aggregate_results --run_id <RUN_ID>


Artifacts appear under:

results/<RUN_ID>/tau_risky_real/{rows.jsonl,run.json}
results/LATEST/{summary.csv,summary.svg,index.html}
```

## CI usage

GitHub → Actions → run-real-mvp → Run workflow

Inputs: model (default llama-3.1-8b-instant), trials, seeds

Artifacts to download

latest-artifacts/ for a quick look

run-<timestamp>.zip for the full folder

## Data layout (contract)

Rows: one JSON object per trial with run_id, exp, seed, trial, model, latency_ms, tokens, success, judge_score, fail_reason, pre_call_gate, post_call_gate, input_case, timestamp

Run audit (run.json): start/finish timestamps and gate audit entries; next: gate_summary (see EXP-002)

## Governance (MVP)

Pre/post gates are currently simple (amount thresholds + approval mention).

Next: declarative policy rules + structured GateDecision + CI “GATES” summary (EXP-002).

## Troubleshooting

Empty HTML/CSV/SVG: Check rows.jsonl exists and has ≥1 line.

All trials denied (pre-gate): Report will show “0 evaluated calls”; review policy thresholds.

Missing secret: Ensure GROQ_API_KEY is set in repo secrets and available to the workflow job.

Wrong run opened: make report uses RUN_ID or LATEST; pass --run_id explicitly to target a specific run.

## Why this exists
Teams need **fast iteration** and **CI-friendly artifacts** to reason about agent risks in context—and a simple way to reach a **first REAL MVP**. DoomArena-Lab gives you:
- **SHIM** — simulation adapters for quick, deterministic demos.
- **REAL** — upstream DoomArena adapters when available (fallback to SHIM when not).
- **Artifacts** — timestamped run dirs + “latest” copies; SVG plots embed nicely in PRs.

## Artifacts & schema
- Each run writes to `results/<RUN_ID>/`; convenience copies go to `results/LATEST/*`.
- Canonical files in `results/<RUN_ID>/`: `index.html`, `summary.csv`, `summary.svg`, `summary.md`, `run.json`, `notes.md`, plus per-experiment subfolders.
- CSV includes `summary_schema: 1`; run metadata includes `results_schema: 1`.
- The `run-demo` GitHub Action uploads **latest-artifacts** for quick inspection and a slimmed `run-<RUN_ID>` folder for pinned references.

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
- **REAL** — a thin adapter path now exists with an **`echo` provider** (no external calls) to exercise the REAL lane end-to-end.
  - Metadata is recorded in `results/<RUN_ID>/run.json` under `.real` (provider/model/key env, healthcheck).
  - Use **Actions → `run-real-mvp`** to run with `MODE=REAL` (manual, secrets-aware). A true provider can be added next.

## Policy tags & routing
- Add `policy: benign|sensitive|prohibited` to each experiment config.
- Only `benign` experiments will hit REAL providers by default.
- Marking a config `policy: sensitive` routes MODE=REAL → SHIM unless you export `ALLOW_SENSITIVE=1`.
- `policy: prohibited` always runs via SHIM. Each run records the decision in `results/<RUN_ID>/run.json`.

## Make targets (TL;DR)
- `make help` — list common targets & docs.
- `make demo` — tiny sweep (defaults to SHIM) producing `results/<RUN_ID>/`.
- `make xsweep CONFIG=...` — run a configurable sweep.
- `make report` — asserts `summary.csv`/`summary.svg`; updates `results/LATEST`.
- `make latest` — refreshes `results/LATEST` to the newest valid run.
- `make open-artifacts` — opens `results/LATEST/summary.svg` and `summary.csv`.
- `make list-runs` — list timestamped run folders with quick validity flags.
- `make tidy-run RUN_ID=...` — remove redundant files in a run folder (keeps canonical ones).
- `make quickstart` — `install → demo → report → open-artifacts`.

## Docs
- [Architecture](docs/ARCHITECTURE.md) — data flow, contracts, schemas, CI
- [Experiments](docs/EXPERIMENTS.md) — add/run configs, thresholds, tips

### Testing
✅ `pytest tests/test_lib.py -q` — shared helper unit tests.

✅ `make report` — asserts presence and shape of canonical artifacts.

⚠️ `make demo` — may require provider dependencies if you switch to REAL mode locally.

## CI
The smoke workflow runs a tiny SHIM sweep and publishes artifacts. It also updates `results/LATEST` for quick inspection in PRs.

## Roadmap (short)
- REAL MVP (priority): thin client + MODE=REAL lane for one config, manual Action run-real-mvp, env-based credentials, safe defaults (low trials/seeds).
- Richer report (markdown/HTML summary, per-exp drill-downs)

## Contributing
PRs welcome. Keep demos fast and artifacts reproducible. Aim for small, reviewable changes.


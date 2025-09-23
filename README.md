# DoomArena-Lab

## DoomArena-Lab — what it is and why it exists

**DoomArena-Lab** is a lightweight playground for **grounded agent security & safety experiments**. It helps small teams move fast from *prompts* to *plans* to *evidence*: run tiny, repeatable SHIM demos today, then flip on REAL adapters to cloud models as they become available—all with CI-friendly artifacts you can review in a PR.

### The problem we’re solving
- Most agent testing is **generic and one-shot**. Real agents are loops (Goal → Plan → Tools → Env → Memory → Feedback) and their risks show up **between** the boxes.
- Teams need **cheap, deterministic, and explainable** experiments they can run in CI—*before* they commit to heavy frameworks or expensive eval suites.
- Security reviewers want **governance signals** (allow/warn/deny decisions, reasons, audit) next to success/ASR metrics—not a blank HTML page.

### Who this is for
- **Applied AI teams** shipping agentic features who need a **first, credible MVP** of safety & security testing with artifacts leadership can read.
- **Security/Trust reviewers** who need a **gate-aware** view of runs (what was blocked, why) and a low-friction way to comment in PRs.
- **Researchers** who want a minimal harness to try risky slices without adopting a large platform on day one.

### How this differs from the upstream **DoomArena** repo
- **Scope:** Upstream is a full evaluation framework. **DoomArena-Lab** is a **small companion**: opinionated scripts, fixtures, and CI layouts for a *lean* end-to-end.
- **Velocity over breadth:** We prioritize **one real slice** working cleanly (rows → CSV/SVG/HTML + governance) over many benchmarks.
- **Governance-first ergonomics:** Built-in policy gates (allow/warn/deny), audit trails, and gate-aware reports—so results are **interpretable**.
- **Cost discipline:** Defaults to **low-cost models** and small trials; artifacts make token/cost visible.

### Where we are today (MVP status)
- **REAL risky slice** writes per-trial JSONL rows and run audit.
- **Aggregator** emits `summary.csv`, `summary.svg`, and `index.html`.
- **Basic governance hooks**: pre/post gates logged per trial (tightening in progress).

### Where we’re going (next few weeks)
- **Gate tightening & policy config** (structured decisions, reasons, CI “GATES” summary).
- **Gate-aware reports** (clear banners for all-pre-denied/no-data, top reasons, pass-rate over callable trials).
- **CI guardrails** (human-readable failure/warn messages) and simple **cost/volume controls**.
- Optional: **provider matrix** (Groq/OpenAI/Local) and **τ-Bench interop** for offline comparisons.

## What’s new (MVP progress)
- **REAL risky slice now writes rows** → `results/<RUN_ID>/tau_risky_real/rows.jsonl` + `run.json`
- **Aggregation works end-to-end** → `results/LATEST/summary.csv`, `summary.svg`, `index.html`
- **Basic governance hooks** → pre/post gates recorded in rows and audited in `run.json`
- **CI workflows**
  - `run-demo`: local logic smoke; uploads artifacts  
  - `run-real-mvp`: Groq model, manual dispatch with inputs (model, trials, seed)

## Quickstart
```bash
pip install -r requirements-ci.txt   # or: make install

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

## Why this exists
- Enable **fast iteration** with **CI-friendly artifacts** you can attach to PRs.
- Provide **SHIM** simulation adapters for deterministic demos and a **REAL** path to cloud models.
- Keep runs **cheap, auditable, and explainable** (governance signals + metrics).

### Cost & volume controls
- `--max-trials` — optional cap on callable trials (defaults to `--trials` value)
- `--max-total-tokens` — run-level total token ceiling (default `100000`)
- `--max-prompt-tokens` — prompt token ceiling (default `80000`)
- `--max-completion-tokens` — completion token ceiling (default `40000`)
- `--max-calls` — cap provider calls for the run (no cap by default)
- `--temperature` — sampling temperature (default `0.2`)
- `--dry-run` — exercise gating/bookkeeping without calling the provider
- `--fail-on-budget` — exit non-zero if any ceiling is reached

Example:

```
python -m scripts.experiments.tau_risky_real \
  --trials 6 \
  --max-total-tokens 5000 \
  --max-calls 2 \
  --fail-on-budget
```

The GitHub Action exposes the same inputs (`max_trails`/`max_trials`, `max_total_tokens`, `max_prompt_tokens`, `max_completion_tokens`, `max_calls`, `temperature`, `dry_run`, `fail_on_budget`). Run outputs include a single `BUDGET:` line plus budget usage in `run.json`, `summary.csv`, and `index.html`.

## Artifacts & schema
- Each run writes to `results/<RUN_ID>/`; convenience copies go to `results/LATEST/*`.
- Canonical files in `results/<RUN_ID>/`:
  - `index.html` — human summary (gate-aware)
  - `summary.csv` — tabular metrics (append-only schema)
  - `summary.svg` — simple plot for PRs
  - `run.json` — run metadata + **gate audit**
  - Per-experiment folders (e.g., `tau_risky_real/rows.jsonl`)
- Optional **thresholds** in `thresholds.yaml` (run-level mins/maxes + policy) drive CI status after aggregation.

### Thresholds & CI status
`tools/check_thresholds.py` reads run metrics + `thresholds.yaml` and prints an `OK/WARN/FAIL` line:

```yaml
version: 1
min_total_trials: 1
min_callable_trials: 1
min_pass_rate: 0.50
max_post_deny: 0
policy: warn
```

Run `make check-thresholds` locally (`STRICT=1 make check-thresholds` to fail). In Actions → `run-real-mvp`, set `STRICT=1` to turn WARN into FAIL.

## CI usage
- **GitHub → Actions → `run-real-mvp` → Run workflow**
  - **Inputs:** `model` (default `llama-3.1-8b-instant`), `trials`, `seeds`
- **Artifacts to download**
  - `latest-artifacts/` — quick look
  - `run-<timestamp>.zip` — full per-run folder

## Data layout (contract)
- **Rows (per trial):** JSON object with  
  `run_id, exp, seed, trial, model, latency_ms, prompt_tokens, completion_tokens, total_tokens, cost_usd, success, judge_score, fail_reason, pre_call_gate, post_call_gate, input_case, timestamp`
- **Run audit (`run.json`):** start/finish timestamps and gate audit entries.  
  *Next:* `gate_summary` + CI “GATES” line (see EXP-002).

## Governance (MVP)
- **Pre/post gates:** currently simple (amount thresholds + approval mention).
- **Near-term:** declarative policy rules, structured `GateDecision`, reason codes, and a visible CI summary.

### Evaluator rules
- Runtime success criteria live in `policies/evaluator.yaml` (versioned list of `id`/`applies_if`/`success_if`).
- Experiments and the aggregator load the rules at startup (`--evaluator <path>` overrides the default file).
- Each trial records `judge_rule_id`, `callable`, and `success`; run metadata tracks the evaluator version and active rules.
- If the rules file is missing or invalid the workflow fails early with a message pointing to `--evaluator`.

## Troubleshooting
- **Empty HTML/CSV/SVG:** Ensure `results/<RUN_ID>/tau_risky_real/rows.jsonl` exists and has ≥1 line.
- **All trials denied (pre-gate):** Report will show “0 evaluated calls”; review policy thresholds/policy file.
- **Missing secret:** Set repo secret **`GROQ_API_KEY`** and make sure the workflow has access.
- **Wrong run opened:** `make report` uses `RUN_ID` or `LATEST`; pass `--run_id <RUN_ID>` explicitly.

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

PR runs use a dry-run (no provider calls) to keep CI safe and secret-free. REAL provider calls run on push to main with GROQ_API_KEY.

## Roadmap (short)
- REAL MVP (priority): thin client + MODE=REAL lane for one config, manual Action run-real-mvp, env-based credentials, safe defaults (low trials/seeds).
- Richer report (markdown/HTML summary, per-exp drill-downs)

## Contributing
PRs welcome. Keep demos fast and artifacts reproducible. Aim for small, reviewable changes.


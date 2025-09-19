# Backlog

## Goals (north star)
- Ship an **e2e-running** lab that produces small, repeatable experiments with CI-friendly artifacts.
- Support **SHIM** sims for fast iteration **and** a path to **REAL** adapters (first MVP: one cloud model).
- Keep the repo light/approachable: Makefile “buttons”, thin scripts, minimal deps, artifacts you can paste in PRs.

## Near-term (2–5 days, e2e-first)
1) **Run-demo one-click E2E** (CI) — ✅
   - `Actions → run-demo`: runs two SHIM configs, publishes `results/LATEST/*`, uploads `run-<RUN_ID>/` artifact.
   - Pinned `RUN_ID` across steps; artifacts slimmed (no dup timestamped files). ✅
2) **Artifacts hygiene** — ✅
   - Canonical files only in `results/<RUN_ID>/`: `index.html`, `summary.{csv,svg,md}`, `run.json`, `notes.md`, per-exp folders.
   - Convenience copies live in `results/LATEST/*`.
3) **Makefile UX** — ✅ (new/updated)
   - `help`, `vars`, `latest`, `open-artifacts`, `list-runs`, `tidy-run` (remove redundancies).
4) **Docs parity** — ✅
   - README Quick Start reflects `run-demo`, artifacts policy, and E2E story.

## Next up (to real MVP)
### A. REAL MVP (first cloud model) — **priority**
**Why**: E2E without an actual model isn’t a true MVP. We need one “REAL” lane to prove value for product/governance teams.
**Definition of done**:
- `MODE=REAL` path exists for one exp (e.g., `airline_static_v1`).
- Thin adapter module (no heavy framework): takes prompt(s) → calls provider → returns text.
- Configurable via `configs/<exp>/run.yaml` with `provider`, `model`, and `env var` key names.
- Local: developer runs `make demo MODE=REAL` using env vars.
- CI (optional, non-required): a **manual** workflow `run-real-mvp` that reads `secrets.*` and uploads artifacts (not a required check).
**Tasks**:
1. `adapters/real_client.py` (tiny):
   - `class RealClient(provider:str, model:str, api_key_env:str)` with `generate(prompt:str) -> str`.
   - Provider-agnostic shim; implement one provider first (HTTP POST), errors become failed trials.
2. Wire REAL into `scripts/run_experiment.py`:
   - If `MODE=REAL`, instantiate `RealClient` from config; SHIM path unchanged.
3. Config + secrets:
   - Add fields to `configs/airline_static_v1/run.yaml`: `provider`, `model`, `api_key_env`.
   - README snippet: export env var locally; GitHub Actions: inputs map to `${{ secrets.* }}` for **manual** workflow.
4. Workflow:
   - New `.github/workflows/run-real-mvp.yml` (workflow_dispatch): install → `make demo MODE=REAL` (with safe default TRIALS=1, SEEDS=1) → `make report latest` → upload artifacts. Not required for PRs.
5. Guardrails:
   - Timeouts/retries in adapter; redact secrets from logs; cap tokens/price via config.

### B. Test coverage on behavior (fast)
1. Unit test for trial-weighted micro-average in `scripts/_lib.py`. ✅ basic added; extend with edge-cases (0 trials, mixed seeds).
2. “Smoke+assert” on CSV header & non-empty rows for SHIM/REAL E2E (behind an env flag for REAL).

### C. Developer UX polish (quick wins)
1. `make quickstart` — `install → demo → report → open-artifacts` (exists). Expand README.
2. `make list-runs` formatting tweaks (column widths) — optional.
3. `make vars` prints effective config incl. MODE/RUN_ID (exists).

## Tech debt (keep light)
**We keep speed, but centralize the sharp bits:**
1) **Shared helpers** — ✅ `scripts/_lib.py` (CSV read, weighted ASR, ensure_dir, now_iso/git_info).
2) **Explicit contracts** — Add `summary_schema: 1`, `results_schema: 1` (in CSV, run.json). ✅
3) **Docs (1 page each)** — ✅ `docs/ARCHITECTURE.md`, `docs/EXPERIMENTS.md`. Keep tiny.
4) **Makefile help/vars** — ✅ self-documenting.
5) **Don’t** package-ify yet; wait for second REAL provider to emerge before extracting a package.

## Done / Recently shipped
- `run-demo` (pinned RUN_ID, slim artifacts), `list-runs`, `tidy-run`, LATEST pointer helpers, README refresh.

## Nice-to-have (later)
- Optional HTML report enhancements (per-exp drill-down links to per-seed JSONL if produced).
- CI matrix for multiple SHIM configs (kept optional to stay fast).

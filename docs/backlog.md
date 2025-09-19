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
**Why**: E2E without a real model isn’t a true MVP for product/governance review.
**Provider choice**:
- **Default**: **Groq Llama 3.1 8B (instant)** — very low cost and fast; ideal for iterative demos.
- **Backup**: **Google Gemini 1.5 Flash** — also inexpensive with a free tier; keep as alternative path.
**Sizing today**: with TRIALS=3, SEEDS=2 (~6 calls/run), costs are fractions of a cent on Groq; affordable on Gemini. (Costs scale linearly with trials/seeds.)
**Definition of done**:
- `MODE=REAL` runs for `airline_static_v1` using Groq; artifacts identical to SHIM path.
- `RealClient.generate()` implements Groq HTTP with timeout and token caps; model/env configured via YAML (`provider`, `model`, `api_key_env`).
- **Manual** workflow `run-real-mvp` reads `REAL_API_KEY` secret and publishes artifacts; not required for PRs.
**Tasks**:
1. Implement Groq HTTP in `adapters/real_client.py` behind provider `"groq"`; keep `"echo"` for offline tests.
2. Add config examples:
   ```yaml
   provider: groq
   model: llama-3.1-8b-instant
   api_key_env: REAL_API_KEY
   ```
3. Add `tools/estimate_cost.py` (optional) + `make estimate-cost` to project run cost (TOK_IN/TOK_OUT, TRIALS/SEEDS).
4. `run.json` enrichment: record provider/model and a **cost_estimate** per run (header-level).
5. Docs: README snippet for setting `REAL_API_KEY` (Actions secret + local `.env`).

### B. Governance & policy gates — **expand**
**Why**: Keep security research productive while respecting provider AUPs.
**Done**: baseline policy gate routing (`policy: benign|sensitive|prohibited`) with override env (`ALLOW_SENSITIVE=1`), decision recorded in `run.json`.
**Next**:
1. **Benign surrogate** mechanism: allow configs to specify placeholder payloads for sensitive tests (exercise control flow without AUP violations).
2. **REAL thresholds**: extend thresholds.yaml with optional `real:` block (e.g., higher `min_trials`), post in PR comment; keep warn-only by default.
3. **Audit log**: append a `policy_decisions` array in `run.json` (per exp) for downstream reporting.
4. **Docs**: AUP quick references; examples of sensitive → surrogate rewrites.

### C. Test coverage on behavior (fast)
1. Unit test for trial-weighted micro-average in `scripts/_lib.py`. ✅ basic added; extend with edge-cases (0 trials, mixed seeds).
2. “Smoke+assert” on CSV header & non-empty rows for SHIM/REAL E2E (behind an env flag for REAL).

### D. Developer UX polish (quick wins)
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

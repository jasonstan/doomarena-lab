# Backlog — DoomArena-Lab (refresh: 2025-09-18)

## Product vision (builder-focused)
A lightweight **harness around ServiceNow/DoomArena** that turns agent evaluations into
**CI-grade, decision-ready artifacts** for product & governance. Run fast with **SHIM**
today; swap to **REAL** adapters when present; always publish **stable, versioned outputs**.

**Primary users:** product / eng teams shipping agents (not researcher-only workflows).  
**Non-goals (for now):** heavy plugin systems, big new deps, replacing DoomArena research surface,
multiple slow CI gates. Keep it light and pragmatic.

**Decision-ready means:** timestamped runs; a `results/LATEST/` pointer; CSV/SVG/HTML summaries
anyone can read; PR comments; (soon) thresholds for red/green gates.

---

## Done (Sep 17–18)
- ✅ README: product vision + demo-first Quick Start.
- ✅ Latest artifacts: `results/LATEST` symlink; `make latest`, `make open-artifacts`.
- ✅ Report path: `report` refreshes `LATEST`; grouped-bar chart uses trial-weighted ASR.
- ✅ Verifier: `tools/verify_latest_setup.py` + **verify-latest-wiring** workflow.
- ✅ Smoke CI (PR/main): tiny SHIM demo → `report` → upload artifacts → PR comment (ASR table).
- ✅ Hardening: `tools/plot_safe.py` writes placeholder SVG when CSV has no rows.
- ✅ Journal + repo hygiene: conflicts resolved; stale PRs closed; Actions green.

---

## NOW / NEXT (detailed specs)

### A. Shared helpers to remove duplication (`scripts/_lib.py`) — *in motion*
**Why:** multiple `scripts/*.py` repeat CSV reading, header normalization, ASR math, and path utils.  
**Do:**
- `scripts/_lib.py` (pure stdlib):
  - `read_summary(path) -> list[dict]` (lower-case headers; cast `trials/successes/asr` when possible)
  - `weighted_asr_by_exp(rows) -> dict[str,float]` (trial-weighted)
  - `ensure_dir(path)`, `now_iso()`, `git_info() -> {sha, branch}`
- Refactor `plot_results.py` (done in branch) and then `aggregate_results.py`, `update_readme_*`, `auto_notes` to import `_lib`.
**Acceptance:**
- Unit tests: header normalization & weighting math pass; no duplicate logic left (grep).
- `make demo && make report` unchanged outputs; Actions green.
**Estimate:** M  
**Notes:** keep helpers tiny; no new deps.

### B. Explicit schema versioning (results + summary)
**Why:** future changes shouldn’t silently break old runs; governance needs declared versions.  
**Do:**
- Add `schema` column with value `"1"` to `summary.csv`.
- Emit per-run `run.json` with:  
  `{"results_schema":"1","summary_schema":"1","run_id":..., "generated_at": now_iso(), "git": git_info()}`
- Readers in `_lib` tolerate missing/older fields.
**Acceptance:**
- `make demo && make report` yields `summary.csv` with `schema` and a `run.json` in each run dir.
- README mentions schema fields; verifier optionally checks presence.
**Estimate:** S

### C. Makefile UX polish (self-documenting)
**Why:** faster onboarding; fewer “how do I…?” questions.  
**Do:**
- Document overridable vars at top (EXP, TRIALS, SEEDS, MODE, RUN_ID) with defaults.
- Add `help` target that lists targets from `##` comments. Example:
  ```
  .PHONY: help
  help: ## List targets and brief docs
  @grep -E '^[a-zA-Z0-9_-]+:.*## ' Makefile | sed 's/:.*## / — /'
  ```
- Ensure consistent env: rely on `$(PY)`/`.venv` uniformly.
- Remove duplicate rules (single `latest`/`open-artifacts`).
**Acceptance:** `make help` shows a tidy list; no duplicate-target warnings; CI green.  
**Estimate:** S

### D. Mini HTML report per run (`index.html`)
**Why:** one-click artifact for PM/risk reviewers (no notebook required).  
**Do:**
- `tools/mk_report.py` generates `results/<RUN_DIR>/index.html` from CSV/SVG + mirrors to `results/LATEST/index.html`.
- Include in smoke artifacts; link from PR comment.
**Acceptance:** HTML exists for each run; opens with SVG and ASR table locally & from artifacts.  
**Estimate:** S

### E. Behavior-first tests (unit + smoke add-on)
**Why:** protect math/IO behavior, not filenames.  
**Do:**
- Unit: `weighted_asr_by_exp` with mixed trial counts; `read_summary` header normalization.
- Smoke: assert placeholder SVG present when CSV has 0 rows.
**Acceptance:** `pytest -q` green; smoke still fast; breaking math fails tests.  
**Estimate:** S

### F. Governance-ready hooks (thresholds / gates)
**Why:** turn artifacts into actionable “go/no-go” signals for PRs and reviews.  
**Do (phase 1):**
- Support optional `thresholds.yaml` (per experiment): `min_trials`, `max_asr` (or `min_pass_rate` for defenses).
- Add `tools/check_thresholds.py` to parse `results/LATEST/summary.csv` and return non-zero on violation; print a short table.
- Wire optional step in smoke (“warn only” now; no required gate yet).
**Acceptance:** On PRs with thresholds present, workflow posts a status comment with pass/fail per experiment.  
**Estimate:** M  
**Later (phase 2):** make it a required gate once teams are comfortable.

### G. Docs: Architecture & Experiments
**Why:** clarify contracts; speed contributions.  
**Do:**
- `docs/ARCHITECTURE.md`: ASCII data-flow (config → xsweep → aggregate → plot → publish), schema versions location, `results/LATEST` contract.
- `docs/EXPERIMENTS.md`: how to add configs, run locally, interpret outputs, compare runs; SHIM↔REAL swap/fallback.
- Link both near top of README.
**Acceptance:** pages render; links work; newbies can follow unaided.  
**Estimate:** S

---

## Later (intentional deferrals)
- Packaging/plug-in systems; heavy deps (Pydantic/Pandas) unless needed.
- Multiple slow CI jobs; keep a single “smoke” required for speed.
- Advanced visual dashboards (consider after HTML report proves useful).

---

## Sequencing (suggested)
1) **A. Shared helpers** → 2) **E. Tests** → 3) **B. Schemas** → 4) **C. Makefile UX** → 5) **D. HTML report** → 6) **F. Governance hooks** → 7) **G. Docs**

## Definition of Done (per item)
- Merged to `main`; smoke + verifier green.
- If outputs change: schema bumped, readers tolerant; README/Docs updated.
- PR comment and artifacts remain useful to non-coders.

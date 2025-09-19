# Backlog — DoomArena-Lab (refresh: 2025-09-18)

## North-star
Stay **demo-first** and **artifact-driven** while trimming tech debt that slows changes.
Four thin layers:
1) **Core helpers** (`scripts/_lib.py`) – pure Python, no CLI
2) **CLIs** (`scripts/*.py`) – only arg-parsing + file paths, call helpers
3) **Orchestration** (Make/CI) – the “buttons”
4) **Docs** – dataflow & authoring guides

---

## Done (Sep 17–18)
- ✅ README: product vision + demo-first Quick Start.
- ✅ Latest artifacts UX: `results/LATEST` symlink; `make latest`, `make open-artifacts`.
- ✅ Report path: `report: … latest …`; trial-weighted ASR chart documented.
- ✅ Verifier: `tools/verify_latest_setup.py` + **verify-latest-wiring** workflow.
- ✅ Smoke CI: SHIM demo → report → upload latest artifacts → PR comment with ASR table.
- ✅ Hardening: `tools/plot_safe.py` writes placeholder SVG when CSV has no rows.

---

## NOW / NEXT (detailed)

### A. **Shared helpers to kill duplication** (scripts/_lib.py)
**Why:** multiple scripts repeat CSV header-normalization, ASR math, path utils.
**Do:**
- Create `scripts/_lib.py` with:
  - `read_summary(path) -> list[dict]` (lower-case headers; cast `asr`, `trials`, `successes` to float/int)
  - `weighted_asr_by_exp(rows) -> dict[str,float]`
  - `ensure_dir(path)`, `now_iso()`, `git_info() -> {sha, branch}`
- Refactor `scripts/aggregate_results.py`, `scripts/plot_results.py`, and any notes/README updaters to import from `_lib`.
**Acceptance:**
- Unit tests pass (see “E. Tests” below).
- Grep shows no duplicated CSV/ASR logic in those scripts.
- Smoke/verify workflows still green.
**Estimate:** M
**Risks/Mitigations:** Small behavior drift → keep helper pure and add tests.

### B. **Explicit schema versioning** (results + summary)
**Why:** future changes shouldn’t silently break old runs.
**Do:**
- Add a `schema` column with value `"1"` to `summary.csv`.
- Emit `run.json` (or extend existing metadata) with:
  `{"results_schema":"1","summary_schema":"1","run_id":..., "generated_at": now_iso(), "git": git_info()}`
- Bump versions when columns/semantics change; keep backward-readers in `_lib`.
**Acceptance:**
- `make demo && make report` produces CSV with `schema` column and a `run.json` per run.
- README mentions version fields briefly.
**Estimate:** S

### C. **Makefile UX polish**
**Why:** keep it self-documenting and consistent.
**Do:**
- At top: document overridable vars (EXP, TRIALS, SEEDS, MODE, RUN_ID).
- Add `help` target that lists targets with comments:  
  `help: ## List targets` → grep+sed pattern.
- Ensure consistent venv usage (`$(PY)` or `.venv`) across targets.
- Ensure single definitions for `latest`/`open-artifacts` (no warnings).
**Acceptance:**
- `make help` prints a tidy list; no duplicate-target warnings.
- CI still green.
**Estimate:** S

### D. **Docs: Architecture & Experiments**
**Why:** lowers onboarding cost and clarifies contracts.
**Do:**
- `docs/ARCHITECTURE.md`: data flow (ASCII), where schema versions live, what “published” means.
- `docs/EXPERIMENTS.md`: how to add a config, run locally, read results, compare runs.
- Link both from README (“Learn more”).
**Acceptance:**
- Pages render cleanly; links from README work.
**Estimate:** S

### E. **Behavior-first tests** (unit + smoke add-ons)
**Why:** assert outcomes, not filenames.
**Do:**
- Unit test `weighted_asr_by_exp` (tiny rows; includes mixed trials to prove weighting).
- Unit test `read_summary` header normalization (case variations).
- Keep existing smoke; add a quick check that placeholder SVG exists when CSV empty.
**Acceptance:**
- `pytest -q` green locally and in CI.
- Failing math would break the test.
**Estimate:** S

### F. **Mini HTML report** (lightweight)
**Why:** one-click artifact anyone can read.
**Do:**
- `tools/mk_report.py` to emit `results/<RUN_DIR>/index.html` (+ mirror to `results/LATEST/index.html`): inline SVG object + ASR table.
- Upload in smoke artifacts; link from PR comment.
**Acceptance:** index.html present in artifacts; opens with chart/table locally.
**Estimate:** S

---

## Not now (intentionally deferred)
- Heavy packaging / plugin systems.
- Extra dependencies (Pydantic, Pandas) without need.
- Multiple gated CI jobs; keep single smoke fast.

---

## Sequencing suggestion
1) **A. Shared helpers** → 2) **E. Tests** → 3) **B. Schemas** → 4) **C. Makefile UX** → 5) **D. Docs** → 6) **F. Mini HTML report**

## Definition of Done (for each item)
- Code merged to `main`; smoke + verify workflows green.
- README/Docs updated if user-visible behavior changed.
- If outputs changed: schema bumped and reader handles both new/old.

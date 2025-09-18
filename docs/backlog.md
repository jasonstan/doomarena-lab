# Backlog

This backlog is grouped into **Now (1–3 days)**, **Next (this sprint)**, **Later**, and **Done**.  
Each epic includes *Why*, a set of concrete tasks, and **Acceptance** criteria.

---

## Now (1–3 days)

### 1) Product Vision README (rewrite)
**Why:** Current README reads like a narrow scaffold. We need a clear narrative: this is a *lab* for rapid, reproducible agent-security experiments—demo-first, CI-backed, artifact-centric—complementary to (not a replacement for) ServiceNow/DoomArena.

**Tasks**
- [ ] Rewrite top section: what the lab is, who it’s for, why it’s different/useful.
- [ ] Add **60-second Quick Start** (`make install`, `make demo`, `make open-artifacts`).
- [ ] Explain **SHIM vs REAL** mode and how CI publishes artifacts.
- [ ] Link to **Backlog**, **Architecture**, and **Experiments** docs.
- [ ] Add “Upstream synergy” notes: items we intend to PR back.

**Acceptance**
- README opens with product vision and target users.
- Quick start can be followed verbatim on a clean checkout.
- SHIM/REAL, CI artifacts, and links are present and accurate.
- No code changes; docs-only PR.

---

### 2) Results UX polish: “open-artifacts” & run discovery
**Why:** We now write runs into `${RUN_DIR}` with `notes.md`, but opening artifacts is still manual.

**Tasks**
- [ ] Add `make open-artifacts` to reveal `${RUN_DIR}` (macOS: `open`, Linux: `xdg-open`).
- [ ] Create/maintain `results/LATEST` symlink to the newest `${RUN_DIR}`.
- [ ] Add `scripts/find_runs.py` utility: list runs with `RUN_ID`, exp, mode, timestamp.

**Acceptance**
- After `make demo` or `make xsweep`, `make open-artifacts` opens the latest run.
- `results/LATEST` points to the latest run directory.
- `python scripts/find_runs.py --limit 5` shows recent runs with key fields.

---

### 3) Reporting & Viz: confidence intervals + export PNG/SVG
**Why:** Bar heights now reflect **trial-weighted** ASR; adding CI bars boosts trust and readability.

**Tasks**
- [ ] Compute binomial proportion CIs (e.g., Wilson) per experiment from `successes/trials`.
- [ ] Render error bars on grouped bar chart.
- [ ] Export both **SVG and PNG** to `${RUN_DIR}`.
- [ ] Document interpretation in README “Results” section.

**Acceptance**
- New plot includes error bars.
- Both `summary.svg` and `summary.png` exist in `${RUN_DIR}`.
- README snippet explains CI bars and weighted means.

---

### 4) CI hardening (smoke)
**Why:** Keep PRs healthy and artifacts predictable.

**Tasks**
- [ ] Cache Python deps (Actions `setup-python@v5` with caching), keep YAML lint clean.
- [ ] Upload `${RUN_DIR}/notes.md`, SVG/PNG, and CSVs as artifacts.
- [ ] Retention: 14 days (documented).

**Acceptance**
- Smoke runs green on PRs with artifacts attached.
- Cache hits apparent in Actions logs.
- Retention policy visible in the workflow.

---

## Next (this sprint)

### 5) Architecture doc (dataflow & layering)
**Why:** Make the adapter factory, SHIM/REAL fallback, and results pipeline obvious.

**Tasks**
- [ ] `docs/ARCHITECTURE.md` with ASCII dataflow (config → runner → adapter → results → report).
- [ ] Explain where DoomArena real adapters plug in vs SHIM.
- [ ] Call out extension points.

**Acceptance**
- One-page doc with diagram + bullets; linked from README.

---

### 6) Experiment scaffolds & ablations
**Why:** Speed up adding new experiments and running controlled variations.

**Tasks**
- [ ] Template config generator (`scripts/new_exp.py`) with seed/trial boilerplate.
- [ ] Ablation toggles in config (e.g., defense on/off, tool use on/off).
- [ ] README “How to add an experiment” section.

**Acceptance**
- New experiments are 1–2 commands away; ablations compile into the plot.

---

### 7) Code health & tests
**Why:** Keep the lab maintainable as it grows.

**Tasks**
- [ ] Type hints on public functions (plotting, aggregation, adapters).
- [ ] Unit tests for weighted mean + CI calculators.
- [ ] Pre-commit: black/ruff/mdformat.

**Acceptance**
- CI includes unit tests & formatting checks.
- No style drift on new PRs.

---

## Later

### 8) HTML report (stretch)
**Why:** A single HTML artifact with tables, charts, and notes improves sharing.

**Tasks**
- [ ] Generate a minimal static HTML report from `${RUN_DIR}/notes.md` + PNG/SVG/CSV.
- [ ] Optional badge for README linking to latest report artifact.

**Acceptance**
- One-click HTML report artifact appears in CI and locally.

---

### 9) Docs site (optional)
**Why:** Browsable artifacts and how-tos.

**Tasks**
- [ ] GitHub Pages with a simple index to recent runs (static JSON + JS).
- [ ] “Playbook” how-tos (add a dataset, add a defense, read a chart).

**Acceptance**
- Pages builds from `docs/` with a minimal index.

---

## Done (recent)

- ✅ **Timestamped run directories (RUN_DIR) + summary CSV/PNG + grouped bar with trial-weighted ASR.**
- ✅ **Auto-generated `${RUN_DIR}/notes.md`** with config & results summary.
- ✅ **Stabilized smoke workflow** and branch protections.

**Follow-ups captured above:** open-artifacts, LATEST, CI error bars, HTML report.

---

## Candidates for upstream PRs (ServiceNow/DoomArena)

- Micro-average ASR utility (trial-weighted) and grouped bar example.
- “Smoke” Actions template with artifacts upload.
- Timestamped run directory scaffold + `notes.md` pattern.
- Makefile `xsweep/report` ergonomics.

---

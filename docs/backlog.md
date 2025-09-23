<!-- BACKLOG:BEGIN -->

# DoomArena-Lab Backlog

_Last updated: 2025-09-23 (UTC)_

## 🎯 MVP (what “good” looks like)

A single command / CI run that goes from a tiny, declarative **threat model** → **deterministic cases** → **governed execution** on a low-cost model → **gate-aware report** (CSV/SVG/HTML) → **CI verdict** (**OK / WARN / FAIL**).

**Why this matters (value):** teams can turn a written risk/threat model into **evidence** in hours, not weeks—cheaply, repeatably, and with governance you can explain.

## 📏 Success metrics (plain English)

- **Determinism — Same input ⇒ same cases.**  
  What we measure: Given `threat_model.yaml` + seed, `cases.jsonl` and `input_case` order are identical.  
  Why it matters: Enables apples-to-apples comparisons and reproducibility for audits.

- **Callable ratio — How much test surface actually hits the model?**  
  What we measure: `callable_trials / total_trials` (pre-deny removes non-callable).  
  Why it matters: If callable is low, we’re testing policy, not model behavior (a valid outcome, but a different story).

- **Pass-rate over callable — Model quality where it’s allowed to act.**  
  What we measure: `success_count / callable_trials`, with `success` from the declarative evaluator.  
  Why it matters: Primary quality signal; rolls up per slice and over time.

- **Budget adherence — No surprises on cost/time.**  
  What we measure: Whether `max_calls` and `max_total_tokens` were respected; early-stop is indicated in the report.  
  Why it matters: Predictable costs; safe to run in PRs and on main.

- **CI clarity — Everyone knows “did we pass?” in one line.**  
  What we measure: `thresholds.yaml` → **OK/WARN/FAIL** summary printed, with exact reasons (e.g., “callable too low”, “pass-rate below 0.75”).  
  Why it matters: Turns governance targets into an enforceable, visible gate.

- **Onboarding friction — New contributor can run end-to-end in minutes.**  
  What we measure: Fresh clone → `pip install -r requirements-ci.txt` → `make mvp` → `make open-report` works on first try.  
  Why it matters: More contributors, fewer support cycles.

## ✅ / 🟡 — Where we are vs. the bar

| Area | Status | What we have now |
|---|:--:|---|
| **Case generation (translator)** | ✅ | `specs/threat_model.yaml` → deterministic `cases.jsonl` (`input_case`, `amount`, `persona`). |
| **REAL execution + rows** | ✅ | One JSONL row per trial; stable schema; `run.json` metadata. |
| **Governance gates (pre/post)** | ✅ | `policies/gates.yaml`; structured **reason codes**; budget caps; `callable` flag. |
| **Evaluator rules** | ✅ | `policies/evaluator.yaml`; `judge_rule_id`; `success` per row. |
| **Aggregation & report** | ✅ | Status banner; callable/pass panels; top reasons; CSV/SVG/rows links. |
| **Thresholds → CI** | ✅ | `thresholds.yaml` + verifier: prints and sets **OK/WARN/FAIL**. |
| **CI stability & safety** | ✅ | Python 3.11, pinned deps, preflight, PR dry-run, artifacts. |
| **DX one-command run** | ✅ | `make mvp`, `.env.example`, `make open-report`. |
| **Tests (regression)** | ✅ | Offline tests for CLI, determinism, evaluator, thresholds. |
| **Perf & scale guardrails** | 🟡 | MVP scale OK; streaming for very large runs TBD. |
| **Config validation** | 🟡 | Basic checks only; formal schemas TBD. |

## ✅ Recently shipped (highlights)

- **EXP-006 (DX):** `make mvp`, `.env.example`, `make open-report`.  
- **EXP-007:** Threat model → deterministic cases translator.  
- **EXP-008:** Declarative evaluator (`evaluator.yaml`), `judge_rule_id`, `success`.  
- **EXP-009:** `thresholds.yaml` + verifier → **OK/WARN/FAIL** in CI.  
- **EXP-010:** Report polish — status banner, callable/pass panels, top reasons, data links.  
- **EXP-011:** Governance gates v1 — configurable pre/post gates, reason codes, budget caps, audit.  
- **Audit & CI hardening:** Python 3.11, pinned deps, preflight, YAML fixes, artifact guards.  
- **Tests:** Offline regression for CLI, generation, evaluator, thresholds.

## 🧭 On-tap next (1-week plan)

### EXP-012 — **Config validation (schemas + preflight)**
**User story:** As a contributor, if I typo a field in `threat_model.yaml`/`gates.yaml`/`evaluator.yaml`/`thresholds.yaml`, I get a crisp validation error during preflight (which field, why) before any run starts.  
**Value:** Fewer broken runs; faster onboarding; clearer failures.  
**Done when:** JSON Schema (or pydantic) validators run in preflight; invalid configs block with a single human message; README links to schemas.

### EXP-013 — **Streaming / large-run safety**
**User story:** As a maintainer, I can aggregate 50k+ rows with O(1) memory streaming and predictable CI time.  
**Value:** No OOMs; confidence we scale.  
**Done when:** JSONL is processed streaming; no list accumulation on hot paths; test covers a synthetic large file.

### EXP-014 — **Budget & early-stop UX polish**
**User story:** As a user, I set `max_calls`/`max_total_tokens`, see an **Early stop** badge, and the job exits with a friendly note when limits hit.  
**Value:** Clear guardrails for cost/time.  
**Done when:** Consistent budget fields in `run.json`; badge in HTML; thresholds/verifier unchanged.

## ⏱ Near-term (2–3 weeks)

### EXP-015 — **Provider matrix (same slice, multiple backends)**
**User story:** As a platform owner, I flip a selector to run the same slice on Groq/OpenAI/Local and compare CSVs.  
**Value:** Apples-to-apples portability & price/perf compare.  
**Done when:** Adapters share row schema; selector via CLI/workflow; PR runs only the cheap default.

### EXP-016 — **τ-Bench interop (optional adapter)**
**User story:** As a researcher, I export rows to a minimal τ-Bench format and check against its judge/tasks offline.  
**Value:** Bridge to ecosystem; comparisons without CI bloat.  
**Done when:** Tiny export script; no heavy dependency in CI.

### EXP-017 — **Guide: “From threat model to evidence”**
**User story:** As a new team, I follow a 10-minute guide from sample threat model → **OK/WARN/FAIL** report, understanding gates/evaluator/thresholds on the way.  
**Value:** Faster onboarding & alignment.  
**Done when:** Single page tutorial linked from README; validated by PR dry-run.

### EXP-018 — **Observability hooks (lightweight)**
**User story:** As an operator, I enable a debug mode to persist redacted request/response snippets and gate decisions for a few trials.  
**Value:** Faster triage; no secret leakage.  
**Done when:** Redacted snippets in per-run folder; opt-in; off on PR by default.

## 📚 Later / lower-priority backlog

### EXP-019 — **Richer report visuals**
**User story:** As a stakeholder, I see stacked allow/warn/deny by reason, a trend sparkline, and top-N exemplar failures.  
**Value:** Faster, non-engineer insights.  
**Done when:** Add-only charts; no data contract changes.

### EXP-020 — **Result navigation & diff**
**User story:** As a maintainer, I list last N runs and diff summary metrics between any two runs.  
**Value:** Quick regression triage.  
**Done when:** `tools/latest_run.py` gains `--history N`; simple metric diff.

### EXP-021 — **Pip cache in CI**
**User story:** As a contributor, PR runs finish faster via cached wheels for pinned deps.  
**Value:** Faster CI; lower friction.  
**Done when:** `actions/setup-python` cache enabled; measurable time drop.

### EXP-022 — **Security hygiene: secret scanning & log scrubbing**
**User story:** As a maintainer, accidental secrets are blocked in PRs and sensitive text is scrubbed from exceptions.  
**Value:** Lower risk in logs/artifacts.  
**Done when:** Secret scanning on PR; provider error handler redacts response bodies.

## 🧪 Guardrails we keep measuring

- **Determinism rate:** cases order identical for same seed.  
- **Callable ratio:** % of trials reaching provider (pre-deny removed).  
- **Pass-rate over callable:** success / callable (primary quality signal).  
- **Budget adherence:** caps respected; early-stop badge shown when triggered.  
- **CI SLAs:** PR dry-run ≤ **5 min**; main (real) within configured call/token budget.  
- **Onboarding friction:** fresh clone to report in ≤ **3 commands**.

## ⬇️ Displaced (lower priority; preserved)

_(Items auto-moved here from the previous backlog that are not listed above; kept verbatim for traceability.)_

<!-- BACKLOG:END -->

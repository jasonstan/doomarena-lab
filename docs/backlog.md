<!-- BACKLOG:BEGIN -->

# DoomArena-Lab Backlog

_Last updated: 2025-09-23_

## 🎯 What “good” looks like (MVP e2e)
A single command / CI run that goes from a tiny, declarative **threat model** → concrete **test cases** → **governed execution** on a low-cost model → **gate-aware report** (CSV/SVG/HTML) with **explicit thresholds** and a clear **OK/WARN/FAIL** in CI.

### Minimum user story (by end of week)
> Given a one-page `threat_model.yaml` describing risky behaviors (refund limits, approval rules), I can:
> 1) **generate** deterministic test cases,
> 2) **execute** them with policy gates & budgets,
> 3) **produce** a human-readable, gate-aware report,
> 4) **enforce** thresholds (e.g., pass-rate over callable trials ≥ X%) and get a clear **OK/WARN/FAIL** in CI.

_No τ-Bench dependency; lean slice end-to-end._

## ✅ / 🟡 / ❌ — Where we are vs. that bar
- **Generation**
  - ❌ **EXP-007 — Threat model → cases translator.** Need a tiny YAML schema + deterministic case expansion feeding the REAL slice.
- **Execution**
  - ✅ **EXP-001 — REAL slice emits rows** (`rows.jsonl` + `run.json`).
  - ✅ **EXP-002 — Governance gates + audit (structured)**; decisions logged per trial.
  - ✅ **EXP-004 — CI guardrails & messages**; meaningful RUN OK/WARN/FAIL.
  - 🟡 **EXP-005 — Cost/volume controls**; budgets and early-stop reporting being finalized.
- **Aggregation & reporting**
  - ✅ **EXP-003 — Gate-aware aggregation + HTML** (overview, banners, links).
  - ✅ LATEST copying and reproducible structure.
- **Policy/thresholds**
  - ❌ **EXP-009 — Declarative thresholds → CI status** (min trials/callable, pass-rate, post-deny caps).
- **DX/docs**
  - ✅ README story + formatting updated.
  - ✅ Backlog consolidated.
  - 🟡 **EXP-006 (lite)** — convenience: `make mvp`, `.env.example`, `make open-report`.

## 📌 Rationale (what we’re measuring ourselves against)
We’re optimizing for a credible, cheap, repeatable pipeline that converts a **threat model** into **evidence**:
- **Determinism:** same `threat_model.yaml` + seed ⇒ same cases.
- **Governance-aware evidence:** pass-rate over callable trials; allow/warn/deny counts; top reason codes.
- **Cost control:** predictable token/call ceilings; graceful stop on budget.
- **Clarity in CI:** thresholds map to OK/WARN/FAIL; red/yellow banners explain “no data” or “all pre-denied”.

## 🧭 On tap next (current sprint)
- **EXP-007 — Threat model → cases translator (mini)**
  - **Why now:** Eliminates handcrafted prompts; gives a durable, declarative input.
  - **What:** Define `threat_model.yaml` (soft/hard limits, approval cues, amounts grid); translator expands to a deterministic case table (`input_case`, text, hints). Stamp `run.json.generation={source:'threat_model.yaml', seed, cases}`.
  - **Done when:** Same YAML + seed yields the same N cases; rows reference the generation.

- **EXP-008 — Declarative success rules (eval mini)**
  - **Why now:** Make pass/fail explicit and auditable.
  - **What:** Move evaluator rules into `policies/evaluator.yaml` (or JSON). Rows include `judge_rule_id`; report computes pass-rate over callable trials.
  - **Done when:** Evaluator loads rules; report reflects them (no hard-coded logic).

- **EXP-009 — Metric thresholds → CI status**
  - **Why now:** CI should gate quality, not only execution.
  - **What:** Add `thresholds.yaml` with `min_total_trials`, `min_callable_trials`, `min_pass_rate`, `max_post_deny` (optional `max_post_warn`). Verifier prints `THRESHOLDS: OK|WARN|FAIL` and sets job status.
  - **Done when:** CI outcome matches thresholds and prints a one-line summary.

- **EXP-006 (lite) — DX polish**
  - **Why now:** Faster local iteration.
  - **What:** `make mvp` (translator → execute → aggregate), `.env.example`, `make open-report`.

## 🧪 P1 audit fixes (in scope, behavior-preserving)
- **AUD-T01 — REAL slice CLI drift tests**  
  **Why:** Prevent future argparse mismatches.  
  **What:** Add `tests/test_tau_risky_real_cli.py` to assert legacy flags accepted (`--seeds/--outdir/--risk`), `--seed` precedence, dry-run writes `results/.run_id`, aggregator produces `index.html`/`summary.csv`. No provider calls in tests.

- **AUD-CI01 — Stop masking “latest” failures**  
  **Why:** CI must be truthful.  
  **What:** In `run-demo.yml` and `Makefile` `latest` target, remove `|| true` masking; fail with a clear message; still upload prior artifacts.

- **AUD-DOC01 — README install step**  
  **Why:** Avoid ImportErrors for new contributors.  
  **What:** Ensure Quickstart starts with `pip install -r requirements-ci.txt` (or `make install`).

## ✅ Recently done (highlights)
- **#165 #168 #170 — CI hardening & deps**: PR-safe dry-run, artifact guards, `requests`/`numpy 1.26.x`/`pandas 2.2.x`/`matplotlib 3.8.x`, Python 3.11 pin, unified `python -m pip`, preflight script.
- **EXP-001/002/003/004 — Rows, governance audit, gate-aware report, guardrails** integrated.
- **README + backlog** story/formatting improved; duplicate backlog files consolidated.

## ⏱ Near-term priorities (next 1–2 weeks)
- **Complete EXP-005 — Cost/volume controls** (budgets, stopped-early badge, CSV/HTML append-only fields).
- **Finish AUD-T01/AUD-CI01/AUD-DOC01** (tests, CI truthfulness, docs).
- **Kick off EXP-007/008/009** in that order to reach the MVP story.

## 📚 Backlog (later / nice-to-have)
- **EXP-010 — Risky slice task library expansion** (refund variants; tag `input_case`; ≤20 seeds).
- **EXP-011 — τ-Bench interop (optional)** (adapter for offline compare).
- **EXP-012 — Governance visualizations** (stacked a/w/d; top reasons table; policy drift sparkline).
- **EXP-013 — Provider matrix** (Groq/OpenAI/Local via inputs; same row schema).

## ⬇️ Displaced (lower priority; preserved from previous backlog)
_(Auto-collected from the prior backlog content not appearing in the sections above; keep items verbatim for traceability.)_

- **EXP-001 — REAL slice emits JSONL rows**
  **Impact:** Unblocks aggregation; HTML/CSV/SVG now populate from CI.
  **Details:** Writes `rows.jsonl` + `run.json` per run; rows include success/judge flags and gate outcomes (basic).

- **EXP-002 (spec) — Governance gates + audit (tighten)**
  **Impact:** Clear contract for structured gate decisions and audit roll-up.
  **Details:** Policy config file, `GateDecision` shape, gate summary line for CI. (Implementation next.)

- **EXP-002 (impl) — Governance gates + audit**
  **Why now:** Enforceable rules + transparent audit before scaling trials.
  **What to implement:** `GateDecision` schema; policy file; extend rows with `pre_call_gate.*`/`post_call_gate.*`; `run.json.gate_summary`; CI “GATES:” line; “all pre-denied” warning.

- **EXP-003 — Aggregator & report: gate-aware summaries**
  **Why now:** Report should explain outcomes, not just plot pass rates.
  **What to implement:** Compute pass rate, token & latency stats; include gate breakdowns (allow/warn/deny, top reason); clear **No-Data / All-Denied** banner in `index.html`. CSV additions are backward-compatible.

- **EXP-004 — CI guardrails & failure messaging**
  **Rationale:** Fail loud on misconfig (missing secret, zero rows).
  **Detail:** If `rows.jsonl` < trials → fail job with human message; if 0 callable trials (all pre-denied) → succeed with yellow banner + rationale.

- **EXP-005 — Cost/volume controls**
  **Rationale:** Keep runs cheap & deterministic.
  **Detail:** Add `--max_tokens`, `--temperature`, soft ceiling on total tokens per run; CSV shows `total_tokens` and est. `$`.

- **EXP-006 — Repro & DX polish**
  **Rationale:** Smoother local use.
  **Detail:** `make real` prints `RUN_ID`; `make open-report` opens `results/LATEST/index.html`; `.env.example`.

- **EXP-010 — Task library expansion for risky slice**
  **Why:** More realistic refund-like variants.
  **Detail:** Tag `input_case`; ≤20 stable seeds for CI.

- **EXP-011 — τ-Bench interop (optional)**
  **Why:** Align with community formats without CI bloat.
  **Detail:** Adapter layer to ingest/export τ-Bench offline.

- **EXP-012 — Governance visualizations**
  **Why:** Faster triage.
  **Detail:** Stacked bar (allow/warn/deny), top reasons table, “policy drift” sparkline over last N runs.

- **EXP-013 — Provider matrix**
  **Why:** Portability & price/perf comparisons.
  **Detail:** Abstract provider call; Groq/OpenAI/Local via input; same row schema.

<!-- BACKLOG:END -->

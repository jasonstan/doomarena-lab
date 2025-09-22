<!-- BACKLOG:BEGIN -->

# DoomArena-Lab Backlog

_Last updated: 2025-09-22_

## ✅ Recently done
- **EXP-001 — REAL slice emits JSONL rows**  
  **Impact:** Unblocks aggregation; HTML/CSV/SVG now populate from CI.  
  **Details:** Writes `rows.jsonl` + `run.json` per run; rows include success/judge flags and gate outcomes (basic).

- **EXP-002 (spec) — Governance gates + audit (tighten)**  
  **Impact:** Clear contract for structured gate decisions and audit roll-up.  
  **Details:** Policy config file, `GateDecision` shape, gate summary line for CI. (Implementation next.)

## 🎯 On tap next (current sprint)
- **EXP-002 (impl) — Governance gates + audit**  
  **Why now:** Enforceable rules + transparent audit before scaling trials.  
  **What to implement:** `GateDecision` schema; policy file; extend rows with `pre_call_gate.*`/`post_call_gate.*`; `run.json.gate_summary`; CI “GATES:” line; “all pre-denied” warning.

- **EXP-003 — Aggregator & report: gate-aware summaries**  
  **Why now:** Report should explain outcomes, not just plot pass rates.  
  **What to implement:** Compute pass rate, token & latency stats; include gate breakdowns (allow/warn/deny, top reason); clear **No-Data / All-Denied** banner in `index.html`. CSV additions are backward-compatible.

## ⏱ Near-term priorities (next 1–2 weeks)
- **EXP-004 — CI guardrails & failure messaging**  
  **Rationale:** Fail loud on misconfig (missing secret, zero rows).  
  **Detail:** If `rows.jsonl` < trials → fail job with human message; if 0 callable trials (all pre-denied) → succeed with yellow banner + rationale.

- **EXP-005 — Cost/volume controls**  
  **Rationale:** Keep runs cheap & deterministic.  
  **Detail:** Add `--max_tokens`, `--temperature`, soft ceiling on total tokens per run; CSV shows `total_tokens` and est. `$`.

- **EXP-006 — Repro & DX polish**  
  **Rationale:** Smoother local use.  
  **Detail:** `make real` prints `RUN_ID`; `make open-report` opens `results/LATEST/index.html`; `.env.example`.

## 📚 Backlog (later)
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

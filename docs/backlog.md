<!-- BACKLOG:BEGIN -->
DoomArena-Lab Backlog

Last updated: 2025-09-23 (UTC)

🎯 What “good” looks like (MVP e2e)

A single command / CI run that goes from a tiny, declarative threat model → deterministic test cases → governed execution on a low-cost model → gate-aware report (CSV/SVG/HTML) → thresholds verdict (OK/WARN/FAIL) in CI.

Success measures

Determinism: same threat_model.yaml + seed ⇒ same cases & input_case order

Governance evidence: callable vs. pre-denied trials; post-gate reasons; pass-rate over callable

CI clarity & safety: explicit thresholds → OK/WARN/FAIL; PR runs safe (dry-run); main runs real with budgets

Cost: default config runs in pennies

✅ / 🟡 / ❌ — Where we are vs. the bar
Area	Status	What we have now
Case generation (translator)	✅	specs/threat_model.yaml → deterministic cases.jsonl with input_case, amount, persona
REAL execution + rows	✅	Rows JSONL per trial, run.json, stable schema
Governance gates (pre/post)	✅	Config in policies/gates.yaml; reason codes; budget caps; callable flag
Evaluator rules	✅	policies/evaluator.yaml; judge_rule_id; success on each row
Aggregation & report	✅	HTML with status banner, callable/pass panels, top reasons, CSV/SVG links
Thresholds → CI status	✅	thresholds.yaml + verifier prints + sets OK/WARN/FAIL
CI stability & safety	✅	Python 3.11, pinned deps, preflight, dry-run on PR, artifacts always upload
DX one-command run	✅	make mvp, .env.example, make open-report
Tests (regression)	✅	Offline tests for CLI, generation determinism, evaluator, thresholds
Perf & scale guardrails	🟡	Works for MVP sizes; streaming/large-run safeguards are TODO
Config validation	🟡	Basic checks; formal schema validation (YAML/JSON) is TODO

✅ Recently shipped (highlights)

EXP-006 (DX): make mvp, .env.example, make open-report

EXP-007: Threat model → deterministic cases translator

EXP-008: Declarative evaluator (evaluator.yaml), judge_rule_id, success

EXP-009: thresholds.yaml + verifier → OK/WARN/FAIL in CI

EXP-010: Report polish — status banner, callable/pass panels, top reasons, data links

EXP-011: Governance gates v1 — configurable pre/post gates, reason codes, budgets, audit

Audit P0/P1 fixes: CI hardening, deps pins, preflight, YAML fixes, artifact guards

Tests: Offline regression for CLI/generation/evaluator/thresholds

🧭 On tap next (1-week plan)
EXP-012 — Config validation (schemas + preflight)

User story: As a contributor, when I typo a field in threat_model.yaml/gates.yaml/evaluator.yaml/thresholds.yaml, I get a crisp validation error during preflight telling me which field and why, before any run starts.
Value: Catch bad YAML early; keep CI green; faster onboarding.
Acceptance: JSON Schema (or pydantic) validators wired in tools/ci_preflight.py; failing schema blocks run with a clear, single message; README links to schema.

EXP-013 — Streaming/large-run safety

User story: As a maintainer, I can aggregate 50k+ rows using O(1) memory streaming, and CI time stays predictable.
Value: Prevent OOM/spikes; keep aggregation fast as runs grow.
Acceptance: aggregate_results.py streams JSONL; no list accumulation on hot paths; test covers a large synthetic file.

EXP-014 — Budget & early-stop UX polish

User story: As a user, I can set max_calls/max_total_tokens, see an Early stop badge, and the job exits with a friendly note when limits are hit.
Value: Clear guardrails for cost & time.
Acceptance: Consistent budget fields in run.json, HTML badge, thresholds/verifier unaffected.

⏱ Near-term (2–3 weeks)
EXP-015 — Provider matrix (same slice, multiple backends)

User story: As a platform owner, I can flip inputs to run the identical slice on Groq/OpenAI/Local and compare CSVs.
Value: Apples-to-apples comparisons without retooling.
Acceptance: Adapters share the same row schema; selector via CLI/workflow; CI runs the cheap default on PRs.

EXP-016 — τ-Bench interop (optional adapter)

User story: As a researcher, I can export rows to a minimal τ-Bench format and sanity-check against its judge/tasks offline.
Value: Bridge to the broader ecosystem.
Acceptance: Tiny export script; no heavy dependency in CI.

EXP-017 — Docs: “From threat model to evidence” guide

User story: As a new team, I can follow a 10-minute guide to go from a sample threat model to an OK/WARN/FAIL report, understanding gates/evaluator/thresholds.
Value: Crisp onboarding & alignment.
Acceptance: Single-page tutorial linked from README; verified by PR dry-run.

EXP-018 — Observability hooks (lightweight)

User story: As an operator, I can enable a “debug” mode to persist redacted request/response snippets and gate decisions for a few trials.
Value: Faster triage with no secret leaks.
Acceptance: Redacted snippets in per-run folder; opt-in; off on PRs by default.

📚 Later / lower-priority backlog
EXP-019 — Richer report visuals

User story: As a stakeholder, I can see stacked allow/warn/deny by reason, trend sparkline, and top-N failure exemplars.
Value: Quicker insights for non-engineers.
Acceptance: Add-only charts; zero change to data contracts.

EXP-020 — Result navigation & diff

User story: As a maintainer, I can list last N runs, open any report quickly, and diff summary metrics between two runs.
Value: Fast regression triage.
Acceptance: tools/latest_run.py gains --history N; simple metric diff.

EXP-021 — Pip cache in CI

User story: As a contributor, PR runs complete sooner thanks to cached wheels for pinned deps.
Value: Faster CI.
Acceptance: actions/setup-python cache enabled; CI time measurably lower.

EXP-022 — Security hygiene: secret scanning & log scrubbing

User story: As a maintainer, accidental secrets are blocked in PRs and sensitive response text is scrubbed from exceptions.
Value: Lower risk in logs/artifacts.
Acceptance: Secret scanning step on PR; provider error handler redacts bodies.

🧪 Guardrails we’ll keep measuring

Determinism rate: identical cases.jsonl order with same seed (CI test)

Callable ratio: callable / total (pre-denies are intentional)

Pass-rate over callable: success / callable (primary quality signal)

Budget adherence: no step exceeds caps; early-stop badge present when triggered

CI SLAs: PR (dry-run) ≤ 5 min, main (real) within expected token/call budget

Onboarding friction: Quickstart succeeds on fresh clone in ≤ 3 commands

⬇️ Displaced (lower priority; preserved)

No items are being dropped—everything not listed above stays here for tracking. Move items back up when they become relevant.

<!-- BACKLOG:END -->

# Backlog

_Goal_: a **demo-first, deployment-aware lab** that helps product teams run **grounded, repeatable** security/safety tests quickly. SHIM for speed/CI; REAL for truth.

## Done recently
- **Provider probes** (`probe-provider`): Groq/Gemini checks, fixed model IDs, clean reply + usage in Summary.
- **Artifacts**: Reduced redundancy; per-run `run-<RUN_ID>/` + `latest-artifacts/`.
- **REAL MVP slice**: Minimal Groq call → timestamped `results/<RUN_ID>/` with `reply.txt`, `response.json`, `usage.json`, `run.json`.
- **Telemetry/Cost**: Latency + token usage captured; optional cost via env (`GROQ_PRICE_IN_PER_1K`, `GROQ_PRICE_OUT_PER_1K`) and displayed in `index.html`.

## Now / Next (high-leverage)
1. **REAL τ-Bench risky task (MVP)** — _in progress next_
   - **What**: Add a τ-Bench scenario with actual risk (e.g., _PII exfiltration_ or _policy override_), run via Groq, store per-trial JSONL under `results/<RUN_ID>/tau_risky_v1/`, and flow into aggregate/plot/report.
   - **Why**: Demonstrates **real** value: a grounded, risky test with repeatable metrics (ASR, tokens, latency, optional cost).
   - **Spec**:
     - New script: `scripts/experiments/tau_risky_real.py` (OpenAI-compatible client;  simple judge + policy hooks).
     - Config: `configs/tau_risky_v1/run.yaml` with `MODE` switch, provider/model/env keys.
     - Make targets + `run-real-tau-risky.yml` workflow.
     - JSONL fields: `exp, seed, trial, risk_type, success, reply, tokens, latency, cost_usd`.
2. **Policy gates v1** — guardrails before/after model call
   - **What**: `policies/gates.py` with:
     - Pre-call denylist/intents (e.g., explicit unsafe actions).
     - Post-call detectors (basic PII regex; refusal guard; redaction).
     - Write `policy_decisions` into `run.json` and `rec.policy` into JSONL.
   - **Why**: Governance-friendly; makes research vs production boundaries explicit.
3. **Judge clarity (rule-based)** — replace heuristic for success/failure
   - **What**: `judge/rules.py` with explicit criteria per scenario (e.g., must contain refusal cues; must not leak PII).
   - **Why**: Easier to explain and iterate; can later swap to an LLM judge.

## Soon (supporting)
- **Makefile help polish**: `make help` shows REAL targets; docstrings across targets.
- **Docs**: `docs/SECURITY.md` (secrets, forks, environments), `docs/EXPERIMENTS.md` updates for REAL.
- **Cost caps**: Optional `MAX_TOKENS`, `MAX_COST_USD` per run; fail fast when exceeded.

## Later
- **Multi-provider abstraction**: simple factory (Groq, Gemini) for REAL calls.
- **Richer reports**: per-seed breakdowns, distribution plots, and artifact deep-links to raw JSONL/trace.

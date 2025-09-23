# Governance gates configuration

The REAL slice uses a declarative policy file (`policies/gates.yaml`) to make
pre-call and post-call allow/warn/deny decisions. Gates evaluate the incoming
case, the model response, and budget usage, then attach structured decisions to
both the per-trial rows and the run summary.

## Anatomy of `gates.yaml`

```yaml
version: 1
defaults:
  mode: allow          # allow|warn|strict; overridden by $GATES_MODE
pre_call:
  - id: pre_hard_limit
    applies_if:
      task: refund
    deny_if:
      field: amount
      op: ">"
      value_from: policy.hard_limit
    reason_code:
      deny: pre_hard_limit
    message:
      deny: "Requested amount exceeds the hard refund limit."
post_call:
  - id: post_missing_approval
    applies_if:
      all:
        - field: task
          value: refund
        - field: amount
          op: ">"
          value_from: policy.max_without_approval
    deny_if:
      text_not_contains:
        any: [approval, manager]
    reason_code:
      deny: post_missing_approval
limits:
  max_calls: 1            # optional: merge with CLI limits
  max_total_tokens: 5000
```

Key fields:

- **`pre_call` / `post_call`** – ordered lists of rules. Each rule declares an
  `id`, optional `applies_if` guard, and one or more action blocks (`deny_if`,
  `warn_if`, `allow_if`). The first action whose condition is satisfied returns
  a decision.
- **Conditions** – support nested `all` / `any` / `not` blocks, field
  comparisons (`field` + `op` + `value`/`value_from`), and simple text checks
  (`text_contains`, `text_not_contains`, `text_regex`). Context values come from
  the experiment (`task`, `amount`, `policy`, etc.).
- **Reason codes / messages** – set per-action via `reason_code` and `message`
  mappings. If omitted, `deny` defaults to `<rule_id>`, `warn` to
  `<rule_id>_warn`, and `allow` to `<rule_id>_allow`.
- **`limits`** – optional numeric ceilings (`max_calls`, `max_total_tokens`,
  `max_prompt_tokens`, `max_completion_tokens`, `max_trials`). Values merge with
  CLI flags by taking the stricter bound. When a limit is reached the remaining
  trials are marked `pre_gate.decision = deny` with reason code
  `budget_exhausted`.
- **`defaults.mode`** – fallback decision when no rule matches. `allow` (the
  default) returns `policy_default_allow`, `warn` returns
  `policy_default_warn`, and `strict`/`deny` returns `policy_default_deny`.
  Override at runtime with `GATES_MODE=allow|warn|strict`.

## Reason code taxonomy

The report relies on stable codes. The default configuration emits:

| Code | Description |
| --- | --- |
| `pre_hard_limit` | Amount exceeded the hard refund ceiling. |
| `pre_soft_limit_warn` | Amount requires manager approval. |
| `post_missing_approval` | Post-call response lacked an approval acknowledgement. |
| `post_disallowed_phrase` | Model suggested a disallowed action. |
| `budget_exhausted` | A run-level budget ceiling halted further calls. |
| `policy_default_allow` / `policy_default_warn` / `policy_default_deny` | No rule matched; default mode applied. |

Add new codes conservatively so downstream aggregations stay consistent.

## Runtime behaviour

- **Pre-call evaluation** – Runs before any provider call. Deny decisions set
  `callable = false`, write the failure reason, and log the gate event to
  `run.json`.
- **Post-call evaluation** – Runs on the provider response. Results are recorded
  alongside evaluator outcomes but do not override the judge verdict.
- **Structured outputs** – Each row now includes both legacy
  `pre_call_gate`/`post_call_gate` objects (enriched with `policy_id` and
  messages) and the compact `pre_gate`/`post_gate` structures (`decision`,
  `reason_code`, `rule_id`).
- **Run metadata** – `run.json.gates` captures the config path, version, mode,
  and the set of rule identifiers that fired. Aggregation surfaces allow/warn/
  deny counts, top reason codes, and the default mode used.

## Budgets and limits

`limits` in `gates.yaml` act as governance-enforced ceilings. They are merged
with CLI or environment-provided values (`--max-*` flags) so that the stricter
limit always wins. When a limit trips, subsequent trials are skipped with
`fail_reason = "SKIPPED_BUDGET_REACHED"` and a `pre_gate` of
`deny/budget_exhausted` (rule id `limit.<name>`). Reports show the stop reason in
both the overview card and the budget footer.

## Development notes

- Use `tests/test_gates.py` for offline, deterministic policy checks.
- Call `reset_cache()` (from `policies.gates`) when exercising multiple configs
  in one process.
- Invalid or missing configs fail fast with an error that points back to this
  document.

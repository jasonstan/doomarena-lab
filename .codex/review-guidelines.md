# Doomarena-Lab — Review Guidelines

These rules apply to **Codex** and human reviewers. Prefer **safety + testability** over stylistic changes.

## Priorities (highest → lowest)
1) **Correctness & Safety**
   - No unresolved conflicts, no failing tests.
   - No failure-masking: a step that detects an error must **exit non-zero**.
   - Security hygiene: no secrets in code; avoid unsafe eval/exec; sanitize shell and file paths.
2) **Test Quality**
   - Add/keep tests for new or risky paths.
   - Small, fast, deterministic tests preferred.
3) **Operational Clarity**
   - Logs must be actionable (file paths, sizes, IDs).
   - CI must fail loudly on invariant violations (e.g., empty artefacts).
4) **Maintainability**
   - Keep diffs focused; avoid drive-by formatting.
   - Preserve module cohesion; split broad refactors.
5) **Style**
   - Follow existing linters/formatters; do not introduce new style churn in conflict fixes.

## Conflict-resolution policy
- Start from latest `main`.
- Prefer versions that:
  - are covered by tests (existing or added),
  - match current repo patterns (naming, layout, CI hooks),
  - minimize diff size and risk.
- If both branches contain important logic, **compose** them and add tests.
- For non-obvious decisions, add a short “Decision log” note in the PR.

## CI & workflows
- Validators must **fail the job** (exit 1) on violations; do not rely on log text alone.
- Artefacts: HTML ≥ **1 KB** and contains non-empty `<body>…</body>`; SVG > **200 B** and contains drawing tags (`path|rect|circle|line|polyline|polygon`).
- Pin Actions: `uses: owner/action@<sha or tag>` (no floating `@main`).

## Security checklist
- No plaintext secrets; use GitHub Secrets.
- Quote shell variables, avoid `eval`, validate inputs.
- Use OS temp dirs; remove temp files on failure.

## Performance (when touched)
- Avoid obvious O(n²) loops on large inputs.
- Prefer streaming/iterators for large files.

## When to split PRs
- If a fix triggers broad refactors, split into:
  1) behavior fix, 2) refactor follow-up.

## PR summary expectations
- 5–10 bullets: what changed / why.
- Map superseded PRs; note which commits/files were absorbed.

## Tests / Proof
- Draft PR shows:
  - The new file path exists and renders in GitHub.
  - PR template (if present) includes the link line.
- CI is green (no workflow or lint failures).

## Constraints
- No behavior changes to runtime code in this task.
- No new dependencies.

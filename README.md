# TAUBENCH Airline Scaffold

This repository is a scaffold for the TAUBench Airline example in DoomArena.

## Experiments
- Use `make scaffold` once to create folders.
- Edit config at `configs/airline_escalating_v1/run.yaml`.
- Run offline: `make install && make run`
- Tests: `make test`
- Results (JSONL) will be written under `results/`.

### Quickstart (experiments)

```bash
make sweep SEEDS="41,42,43" TRIALS=5 MODE=SHIM
head -5 results/summary.csv
```

> MODE=REAL attempts τ-Bench (requires access).

### Swapping to real DoomArena classes

This repo currently uses thin adapters to mirror DoomArena concepts:

| Lab adapter | DoomArena concept (target) |
| --- | --- |
| `adapters.attacks.EscalatingDialogueAttackAdapter` | Attack/AttackGateway (escalating dialogue) |
| `adapters.filters.OutOfPolicyRefundFilter` | Success predicate / policy filter |

**Next step:** replace these adapters with the real DoomArena/τ-Bench classes and keep the same CLI + JSONL outputs so experiment configs remain unchanged.

## Results
<!-- RESULTS:BEGIN -->

| exp | seed | mode | ASR | trials | successes | path |
| --- | --- | --- | --- | --- | --- | --- |
| airline_escalating_v1 | 43 | SHIM | 0.60 (3/5) | 5 | 3 | [airline_escalating_v1_seed43](results/airline_escalating_v1/airline_escalating_v1_seed43.jsonl) |
| airline_escalating_v1 | 42 | SHIM | 0.60 (3/5) | 5 | 3 | [airline_escalating_v1_seed42](results/airline_escalating_v1/airline_escalating_v1_seed42.jsonl) |
| airline_escalating_v1 | 41 | SHIM | 0.60 (3/5) | 5 | 3 | [airline_escalating_v1_seed41](results/airline_escalating_v1/airline_escalating_v1_seed41.jsonl) |

<!-- RESULTS:END -->

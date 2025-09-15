# TAUBENCH Airline Scaffold

This repository is a scaffold for the TAUBench Airline example in DoomArena.

## Experiments
- Use `make scaffold` once to create folders.
- Edit config at `configs/airline_escalating_v1/run.yaml`.
- Run offline: `make install && make run`
- Tests: `make test`
- Results (JSONL) will be written under `results/`.

### Swapping to real DoomArena classes

This repo currently uses thin adapters to mirror DoomArena concepts:

| Lab adapter | DoomArena concept (target) |
| --- | --- |
| `adapters.attacks.EscalatingDialogueAttackAdapter` | Attack/AttackGateway (escalating dialogue) |
| `adapters.filters.OutOfPolicyRefundFilter` | Success predicate / policy filter |

**Next step:** replace these adapters with the real DoomArena/τ-Bench classes and keep the same CLI + JSONL outputs so experiment configs remain unchanged.

## Results
<!-- RESULTS:BEGIN -->

| run_id | ASR | trials | path |
| --- | --- | --- | --- |
| [airline_escalating_seed42](results/airline_escalating_v1/airline_escalating_seed42.jsonl) | 0.600 | 5 | SHIM |

<!-- RESULTS:END -->

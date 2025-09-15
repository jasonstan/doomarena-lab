# TAUBENCH Airline Scaffold

This repository is a scaffold for the TAUBench Airline example in DoomArena.

## Experiments
- Use `make scaffold` once to create folders.
- Edit config at `configs/airline_escalating_v1/run.yaml`.
- Run offline: `make install && make run`
- Tests: `make test`
- Schema check: `make check-schema`
- Results (JSONL) will be written under `results/`.

### Quickstart (experiments)

```bash
# 3 seeds, 5 trials each (shim)
make sweep3
head -5 results/summary.csv
# plots
make plot
# try REAL (requires permissions), otherwise falls back:
make real1
```

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
| airline_escalating_v1 | 42 | SHIM | 0.60 (3/5) | 5 | 3 | [airline_escalating_v1_seed42](results/airline_escalating_v1/airline_escalating_v1_seed42.jsonl) |

<!-- RESULTS:END -->

### Results schema

`results/summary.csv` is locked to the following header (order matters):

```
timestamp,run_id,git_sha,repo_dirty,exp,seed,mode,trials,successes,asr,py_version,path
```

Use `make check-schema` to verify the file matches the expected schema.

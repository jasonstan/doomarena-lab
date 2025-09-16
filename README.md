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

### Run an experiment

```bash
make xsweep CONFIG=configs/airline_escalating_v1/exp.yaml
head -5 results/summary.csv
ls -R results/*
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

![Results summary](results/summary.svg)

| exp | seeds | mode | ASR | trials | successes | git | run_at |
| --- | --- | --- | --- | --- | --- | --- | --- |
| airline_escalating_v1 | 43,41,42 | SHIM | 0.60 (3/5) | 5 | 3 | c98ef02d | 2025-09-16T08:01:15.606971Z |
| airline_escalating_v1 | 42,41,43 | SHIM | 0.60 (3/5) | 5 | 3 | c98ef02d | 2025-09-16T08:01:12.610826Z |
| airline_escalating_v1 | 41,42,43 | SHIM | 0.60 (3/5) | 5 | 3 | c98ef02d | 2025-09-16T08:01:09.726240Z |

<!-- RESULTS:END -->

### Results schema

Each run writes `results/<exp>/meta.json` with execution metadata. `results/summary.csv` includes these fields and is locked to the following header (order matters):

```
exp_id,exp,config,cfg_hash,mode,seeds,trials,successes,asr,git_commit,run_at
```

Use `make check-schema` to verify the file matches the expected schema.

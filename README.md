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
| airline_escalating_v1 | 42 | SHIM | 0.33 (1/3) | 3 | 1 | 82bdb477 | 2025-09-16T08:57:43.543842Z |
| airline_escalating_v1 | 41 | SHIM | 0.33 (1/3) | 3 | 1 | 82bdb477 | 2025-09-16T08:57:43.370835Z |
| airline_escalating_v1 | 43,41,42 | SHIM | 0.60 (3/5) | 5 | 3 | c98ef02d | 2025-09-16T08:01:15.606971Z |
| airline_escalating_v1 | 42,41,43 | SHIM | 0.60 (3/5) | 5 | 3 | c98ef02d | 2025-09-16T08:01:12.610826Z |
| airline_escalating_v1 | 41,42,43 | SHIM | 0.60 (3/5) | 5 | 3 | c98ef02d | 2025-09-16T08:01:09.726240Z |

<!-- RESULTS:END -->

### Results schema

Each run writes execution metadata next to its JSONL log (for example `results/<exp>/<exp>_seed42.meta.json`). `results/summary.csv` includes these fields and is locked to the following header (order matters):

```
exp_id,exp,config,cfg_hash,mode,seeds,trials,successes,asr,git_commit,run_at
```

Use `make check-schema` to verify the file matches the expected schema.

<!-- TOPN:BEGIN -->
## Latest experiments — Top N by ASR

|rank|exp_id|ASR|mode|trials|seeds|commit|run_at|
|---|---|---|---|---|---|---|---|
|1|airline_escalating_v1:1a1a04db|0.600|SHIM|5|43,41,42|c98ef02|2025-09-16T08:01:15.606971Z|
|2|airline_escalating_v1:1a1a04db|0.600|SHIM|5|42,41,43|c98ef02|2025-09-16T08:01:12.610826Z|
|3|airline_escalating_v1:1a1a04db|0.600|SHIM|5|41,42,43|c98ef02|2025-09-16T08:01:09.726240Z|
|4|airline_escalating_v1:3762657d|0.333|SHIM|3|42|82bdb47|2025-09-16T08:57:43.543842Z|
|5|airline_escalating_v1:3762657d|0.333|SHIM|3|41|82bdb47|2025-09-16T08:57:43.370835Z|
<!-- TOPN:END -->

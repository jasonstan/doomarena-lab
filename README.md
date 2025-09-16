[![Smoke](https://github.com/jasonstan/doomarena-quickstart/actions/workflows/smoke.yml/badge.svg)](https://github.com/jasonstan/doomarena-quickstart/actions/workflows/smoke.yml)

# TAUBENCH Airline Scaffold

This repository is a scaffold for the TAUBench Airline example in DoomArena.

## Experiments
- Use `make scaffold` once to create folders.
- Edit config at `configs/airline_escalating_v1/run.yaml`.
- Run offline: `make install && make run`
- Tests: `make test` (runs demo + results validation)
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

## Testing

`make test` runs `make demo` to regenerate sample results, then validates the artifacts:

- `results/summary.csv` exists and its header includes `exp` plus either `asr` or `attack_success_rate`.
- `results/summary.svg` exists as the aggregate plot.
- At least one per-seed `*seed*.jsonl` file is present under `results/`.

### Quick Demo (compare two experiments)

```bash
make install
make demo
open results/summary.svg   # or download from CI artifacts on the PR
```

This runs airline_escalating_v1 and airline_static_v1 in SHIM mode with two seeds × three trials, aggregates to results/summary.csv, and renders results/summary.svg with one bar per experiment.

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

`make report` also writes `results/summary.md` (a readable notes file) and the CI run uploads it as an artifact.

### Results plot

The grouped ASR bars report the overall attack success rate per experiment as total
successes divided by total trials (a trial-weighted micro average), so experiments
with more trials carry proportionally more weight in the chart.

<!-- RESULTS:BEGIN -->

![Results summary](results/summary.svg)

| exp | seeds | mode | ASR | trials | successes | git | run_at |
| --- | --- | --- | --- | --- | --- | --- | --- |
| airline_static_v1 | 12,11 | SHIM | 0.33 (1/3) | 3 | 1 | 235eb543 | 2025-09-16T16:54:51.365106+00:00 |
| airline_static_v1 | 11,12 | SHIM | 0.33 (1/3) | 3 | 1 | 235eb543 | 2025-09-16T16:54:51.193991+00:00 |
| airline_escalating_v1 | 12 | SHIM | 0.33 (1/3) | 3 | 1 | 235eb543 | 2025-09-16T16:54:50.856852+00:00 |
| airline_escalating_v1 | 11 | SHIM | 0.33 (1/3) | 3 | 1 | 235eb543 | 2025-09-16T16:54:50.677487+00:00 |

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
|1|airline_static_v1:93da93d2|0.333|SHIM|3|12,11|235eb54|2025-09-16T16:54:51.365106+00:00|
|2|airline_static_v1:93da93d2|0.333|SHIM|3|11,12|235eb54|2025-09-16T16:54:51.193991+00:00|
|3|airline_escalating_v1:3762657d|0.333|SHIM|3|12|235eb54|2025-09-16T16:54:50.856852+00:00|
|4|airline_escalating_v1:3762657d|0.333|SHIM|3|11|235eb54|2025-09-16T16:54:50.677487+00:00|
<!-- TOPN:END -->

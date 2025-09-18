[![smoke](https://github.com/jasonstan/doomarena-lab/actions/workflows/smoke.yml/badge.svg?branch=main)](https://github.com/jasonstan/doomarena-lab/actions/workflows/smoke.yml)

# doomarena-lab

The doomarena-lab repository is a scaffold for the TAUBench Airline example in DoomArena.

## Experiments
- Use `make scaffold` once to create folders.
- Edit config at `configs/airline_escalating_v1/run.yaml`.
- Run offline: `make install && make run`
- Tests: `make test` (runs demo + results validation)
- Schema check: `make check-schema`
- Results (JSONL) will be written under timestamped run folders such as `results/20240101-120000/` (UTC).

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

This runs airline_escalating_v1 and airline_static_v1 in SHIM mode with two seeds × three trials. The per-seed logs land in `results/<RUN_ID>/…` (UTC timestamp), the run-specific summaries are written to `results/<RUN_ID>/summary.*`, and `make report` publishes copies to `results/summary.*` for quick inspection.

### Run an experiment

```bash
make xsweep CONFIG=configs/airline_escalating_v1/exp.yaml
make report
head -5 results/summary.csv
RUN_ID=$(make latest)
ls results/$RUN_ID
```

### Running with real DoomArena (optional)

Runs default to the SHIM adapters. When the `doomarena` package is installed locally the runner automatically switches to the real DoomArena / τ-Bench classes whenever `MODE=REAL` is requested; otherwise it prints a warning and falls back to the shim adapters so CI and local demos continue to work.

1. Install the real adapters (if you have access):

   ```bash
   pip install doomarena
   ```

2. Launch a run in REAL mode (falls back to SHIM if imports fail):

   ```bash
   make real1
   make xsweep MODE=REAL CONFIG=configs/airline_escalating_v1/exp.yaml
   ```

   You can also set `DOOMARENA_MODE=REAL` in the environment instead of passing `MODE` on the CLI.

## Results

Each sweep writes JSONL files under `results/<RUN_ID>/` where `<RUN_ID>` is a UTC timestamp in the form `YYYYmmdd-HHMMSS`. Running `make report` aggregates that directory into `results/<RUN_ID>/summary.csv`, `summary.svg`, and `summary.md`, then publishes copies to `results/summary.*` for backwards compatibility. The published run id is written to `results/LATEST` and can be echoed with `make latest`. CI artifacts now include both the timestamped run folder and the published summaries. Each run now writes `${RUN_DIR}/notes.md` with a human-readable summary and chart.

### Results plot

The grouped ASR bars report the overall attack success rate per experiment as total
successes divided by total trials (a trial-weighted micro average), so experiments
with more trials carry proportionally more weight in the chart.

<!-- RESULTS:BEGIN -->

![Results summary](results/summary.svg)

# Experiment summary — 2025-09-18T10:53:03+00:00

- Experiments: 2
- Total trials: 12
- Total successes: 4
- Micro-average ASR: 33.3%

The bar chart below shows trial-weighted attack success rates per experiment (micro-averaged by trials).

![ASR summary](summary.svg)

| Experiment | Trials | Successes | ASR (%) |
| --- | --- | --- | --- |
| airline_escalating_v1 | 6 | 2 | 33.3% |
| airline_static_v1 | 6 | 2 | 33.3% |

---

*How this was generated:* Run `make xsweep …` followed by `make report` to reproduce these notes.

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
|1|airline_static_v1:93da93d2|0.333|SHIM|3|12,11|21fd63e|2025-09-18T10:53:01.330519+00:00|
|2|airline_static_v1:93da93d2|0.333|SHIM|3|11,12|21fd63e|2025-09-18T10:53:01.153808+00:00|
|3|airline_escalating_v1:3762657d|0.333|SHIM|3|12|21fd63e|2025-09-18T10:53:00.634317+00:00|
|4|airline_escalating_v1:3762657d|0.333|SHIM|3|11|21fd63e|2025-09-18T10:53:00.453650+00:00|
<!-- TOPN:END -->


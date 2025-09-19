# Adding & Running Experiments

## 1) Add a config
Create `configs/<exp_name>/run.yaml` (see existing examples under `configs/`).

## 2) Run locally
```bash
make xsweep CONFIG=configs/<exp_name>/run.yaml SEEDS="11,12" TRIALS=3 MODE=SHIM
make report
make open-artifacts   # prints paths to summary.svg/csv
```
You’ll get:
- `results/<RUN_DIR>/summary.csv` (with `schema=1`)
- `results/<RUN_DIR>/summary.svg`
- `results/<RUN_DIR>/run.json`
- `results/LATEST/index.html` (mini HTML report)

## 3) Compare or repeat
- Re-run with different seeds/trials or MODE=REAL (falls back to SHIM).
- `make latest` refreshes the pointer if you create multiple runs.

## 4) Thresholds (optional policy)
Edit `thresholds.yaml` to set guardrails:
```yaml
<exp_name>:
  min_trials: 10
  max_asr: 0.25
```
CI will post PASS/WARN/FAIL in the PR comment.

## 5) Tips
- `make help` — discover targets
- `make vars` — see effective EXP/TRIALS/SEEDS/MODE/RUN_ID
- Keep outputs schema-compatible; bump schema if columns/semantics change.

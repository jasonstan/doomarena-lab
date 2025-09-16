# Backlog

## Done (recent)
- SHIM end-to-end: configs → xsweep → aggregate → summary.csv → summary.png
- CI smoke on PRs via Makefile; artifacts uploaded
- Results aggregator and plotting utility
- Fixed workflow YAML; removed brittle pip cache; branch rules tuned
- Journal scaffolding available

## Now
- Add second experiment config (`airline_static_v1`) and grouped bar plotting
- Add `make demo` + README “Quick Demo” section

## Next
### Epic: Per-run results directories, metadata & summaries

**Why (problem):**  
Today, local and CI runs write to top-level files like `results/summary.csv`, `results/summary.png`, and `results/<exp>/*seed*.jsonl`. Each new run overwrites the previous artifacts, making it hard to keep history, compare runs, or share a single link to “the latest”.

**Goal (what good looks like):**  
- Every run gets its **own directory** with everything needed to understand and reproduce it.  
- A **human-readable note** sits next to the raw data.  
- CI publishes the **whole run directory** as the artifact.  
- We keep an **index** of runs and a **stable “latest”** pointer per experiment.

#### Design overview

**Directory layout**


results/
<exp>/
<run_id>/
run.json
config.yaml
trials.jsonl
summary.csv
summary.png
notes.md
latest -> <run_id>/
index.csv


**Run id format**  
`YYYYmmddTHHMMSSZ-<shortSHA>-<MODE>-s<seedlist>-t<trials>`

**Minimal Makefile changes**
- `RUN_ID`, `OUTDIR`; pass `--outdir` to scripts; manage `latest`; append to `results/index.csv`.

**Metadata (`run.json`)**
```json
{ "run_id": "<run_id>", "timestamp_utc": "...", "git": { "sha": "...", "branch": "..." }, "exp": "...", "mode": "...", "seeds": [..], "trials": 5, "config_hash": "...", "host": { "os": "...", "python": "..." }, "paths": { "trials_jsonl": "trials.jsonl", "summary_csv": "summary.csv", "plot": "summary.png" } }
```


Auto-notes (notes.md)
Short NL summary (design + findings) using run.json + summary.csv.

CI behavior
Upload per-run directory as artifact; update results/index.csv on main.

Out of scope (stretch, later)

report.md single-file story; notebook export with narrative + outputs.

Acceptance criteria

make xsweep … && make report creates run dir with all files; updates latest; appends to results/index.csv.

Plot/CSV are per-run (no global overwrite).

CI artifact contains the run dir.

Risks & mitigations

Symlink fallback to copy; index commits only on main.

Implementation plan

Wire per-run outdir + metadata (xsweep.py, Makefile, aggregate_results.py, plot_results.py, write_run_metadata.py)

Auto-notes (write_notes_md.py)

CI artifact (upload run dir; safe index handling)

- `compare_results.py` (two runs/commits → compare.csv + compare.png)
- Enrich CSV metadata (exp_id, git SHA, timestamp, seeds, trials, mode)
- Concurrency + stability hardening in `smoke.yml`

## Later
- Ablation grid runs and heatmap visualization
- Per-seed distribution plots (box/violin)
- Optional S3/GitHub Pages publishing for charts
- REAL mode integration when `tau_bench` becomes available
- Journal auto-append flag on `make report`

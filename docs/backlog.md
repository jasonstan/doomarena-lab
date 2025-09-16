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
- `compare_results.py` (two runs/commits → compare.csv + compare.png)
- Enrich CSV metadata (exp_id, git SHA, timestamp, seeds, trials, mode)
- Concurrency + stability hardening in `smoke.yml`

## Later
- Ablation grid runs and heatmap visualization
- Per-seed distribution plots (box/violin)
- Optional S3/GitHub Pages publishing for charts
- REAL mode integration when `tau_bench` becomes available
- Journal auto-append flag on `make report`

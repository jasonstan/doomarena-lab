# Backlog — DoomArena-Lab (refresh: 2025-09-18)

## Done (Sep 17–18)
- ✅ **README**: product vision + demo-first Quick Start.
- ✅ **Artifacts UX**: `results/LATEST` symlink; `make latest`, `make open-artifacts`.
- ✅ **Report integration**: `report` refreshes `LATEST`; trial-weighted ASR chart documented.
- ✅ **Verification**: `tools/verify_latest_setup.py` + **verify-latest-wiring** workflow.
- ✅ **Smoke CI**: SHIM demo → report → upload latest artifacts → PR comment with ASR table.
- ✅ **Hardening**: `tools/plot_safe.py` prevents CI failure on empty/invalid summary.

## Now / Next
1. **Mini HTML report per run**  
   - Generate `results/<RUN_DIR>/index.html` and mirror to `results/LATEST/index.html`.  
   - Include in artifacts; link from PR comment.
2. **Richer PR comment**  
   - Add link to `index.html`; consider rendering a tiny inline ASR table thumbnail.
3. **Configs**  
   - Add 1–2 more demo configs; document how to add/extend configs.
4. **REAL adapters parity**  
   - If upstream DoomArena adapters available, add REAL mode demos with SHIM fallback.
5. **Reporting polish**  
   - Markdown/HTML summary with per-exp drill-down; CSV schema checks in CI.

## Later
- Performance & stability passes on CI runtimes and caching.
- Optional: publish `results/LATEST` as a Pages artifact for easy sharing.

---
_Principles_: demo-first; fast iterations; artifacted, reproducible results.


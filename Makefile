# ------------------------------------------------------------------------------
# DoomArena-Lab Makefile
# Overridable variables (set via `make VAR=value ...`)
#   EXP     ?= airline_escalating_v1   # experiment name
#   TRIALS  ?= 5                       # trials per seed
#   SEED    ?= 42                      # single-seed runs
#   SEEDS   ?= 41,42,43                # multi-seed runs
#   MODE    ?= SHIM                    # SHIM or REAL (falls back to SHIM if REAL not present)
#   RUN_ID  ?= (timestamp default)     # results/<RUN_ID>; persisted via results/.run_id
# ------------------------------------------------------------------------------

.PHONY: venv install test run sweep aggregate report scaffold check-schema plot notes sweep3 real1 xrun xsweep xsweep-all topn demo test-unit ci latest tidy-run open-artifacts list-runs journal install-tau help vars

SHELL := /bin/bash

VENV := .venv
PY   := $(VENV)/bin/python
PIP  := $(VENV)/bin/pip
CONFIG ?= configs/airline_escalating_v1/run.yaml
CONFIG_GLOB ?= configs/*/run.yaml
SEED ?= 42
SEEDS ?= 41,42,43
TRIALS ?= 5
EXP ?= airline_escalating_v1
MODE ?= SHIM

MODE_ARG :=
MODE_OVERRIDE :=
ifneq ($(origin MODE), file)
MODE_ARG := --mode $(MODE)
MODE_OVERRIDE := $(MODE)
endif

RESULTS_DIR ?= results
LATEST_LINK ?= $(RESULTS_DIR)/LATEST
PYTHON ?= python3

RUN_ID ?= $(shell date -u "+%Y%m%d-%H%M%S")
RUN_CURRENT := $(RESULTS_DIR)/.run_id
ifeq ($(origin RUN_ID), file)
ifneq ($(wildcard $(RUN_CURRENT)),)
RUN_ID := $(shell cat $(RUN_CURRENT))
endif
endif
RUN_DIR := $(RESULTS_DIR)/$(RUN_ID)

LATEST_STRICT ?= 0

TRIALS_ARG :=
TRIALS_OVERRIDE :=
ifneq ($(origin TRIALS), file)
TRIALS_ARG := --trials $(TRIALS)
TRIALS_OVERRIDE := $(TRIALS)
endif

SEEDS_OVERRIDE :=
ifneq ($(origin SEEDS), file)
SEEDS_OVERRIDE := $(SEEDS)
endif

EXP_OVERRIDE :=
ifneq ($(origin EXP), file)
EXP_OVERRIDE := $(EXP)
endif

venv: ## Create local virtualenv in .venv
	python -m venv $(VENV)
	$(PY) -m pip install -U pip

install: venv ## Install runtime + dev deps into .venv
	$(PIP) install -U doomarena doomarena-taubench pytest pyyaml pandas matplotlib
	$(PY) scripts/ensure_tau_bench.py || (echo "tau_bench unavailable; continuing without real τ-Bench" && exit 0)

check-schema: venv
	$(PY) scripts/check_schema.py

run: install ## Run single experiment (EXP/SEED/TRIALS/MODE) into results/<RUN_DIR>
	. .venv/bin/activate && python scripts/run_batch.py --exp $(EXP) --seeds "$(SEED)" --trials $(TRIALS) --mode $(MODE) --outdir "$(RUN_DIR)"
	printf "%s\n" "$(RUN_ID)" > $(RUN_CURRENT)

.ONESHELL: xrun
xrun:
	if [ -x "$(PY)" ]; then PYTHON_BIN="$(PY)"; else PYTHON_BIN="python"; fi; \
	CMD="$$PYTHON_BIN scripts/run_experiment.py --config $(CONFIG) --seed $(SEED) --outdir \"$(RUN_DIR)\""; \
	if [ -n "$(MODE_OVERRIDE)" ]; then CMD="$$CMD --mode $(MODE_OVERRIDE)"; fi; \
	if [ -n "$(TRIALS_OVERRIDE)" ]; then CMD="$$CMD --trials $(TRIALS_OVERRIDE)"; fi; \
	if [ -n "$(EXP_OVERRIDE)" ]; then CMD="$$CMD --exp $(EXP_OVERRIDE)"; fi; \
	echo "xrun: $$CMD"; \
	eval $$CMD; rc=$$?; if [ $$rc -ne 0 ]; then exit $$rc; fi; \
	printf "%s\n" "$(RUN_ID)" > $(RUN_CURRENT)

sweep: install ## Multi-seed sweep (SEEDS) into results/<RUN_DIR>, then report
	. .venv/bin/activate && python scripts/run_batch.py --exp $(EXP) --seeds "$(SEEDS)" --trials $(TRIALS) --mode $(MODE) --outdir "$(RUN_DIR)"
	printf "%s\n" "$(RUN_ID)" > $(RUN_CURRENT)
	$(MAKE) report RUN_ID=$(RUN_ID)

.PHONY: demo
demo: install ## Tiny SHIM demo (two configs) -> report -> publish latest
	$(MAKE) xsweep CONFIG=configs/airline_escalating_v1/run.yaml EXP=airline_escalating_v1 TRIALS=3 SEEDS="11,12" MODE=SHIM RUN_ID=$(RUN_ID)
	$(MAKE) xsweep CONFIG=configs/airline_static_v1/run.yaml     EXP=airline_static_v1     TRIALS=3 SEEDS="11,12" MODE=SHIM RUN_ID=$(RUN_ID)
	$(MAKE) report RUN_ID=$(RUN_ID)

.ONESHELL: xsweep
xsweep: install ## Configurable sweep from CONFIG -> results/<RUN_DIR>
	mkdir -p "$(RUN_DIR)"
	if [ -x "$(PY)" ]; then PYTHON_BIN="$(PY)"; else PYTHON_BIN="python"; fi; \
	CMD=""$$PYTHON_BIN" "scripts/xsweep.py" --config "$(CONFIG)" --outdir "$(RUN_DIR)""; \
	if [ -n "$(SEEDS_OVERRIDE)" ]; then CMD="$${CMD} --seeds "$(SEEDS_OVERRIDE)""; fi; \
	if [ -n "$(MODE_OVERRIDE)" ]; then CMD="$${CMD} --mode "$(MODE_OVERRIDE)""; fi; \
	if [ -n "$(TRIALS_OVERRIDE)" ]; then CMD="$${CMD} --trials "$(TRIALS_OVERRIDE)""; fi; \
	if [ -n "$(EXP_OVERRIDE)" ]; then CMD="$${CMD} --exp "$(EXP_OVERRIDE)""; fi; \
	echo "xsweep: $$CMD"; \
	eval $$CMD; rc=$$?; if [ $$rc -ne 0 ]; then exit $$rc; fi; \
	printf "%s\n" "$(RUN_ID)" > $(RUN_CURRENT)
sweep3:
	$(MAKE) sweep SEEDS="41,42,43" TRIALS=5 MODE=SHIM RUN_ID=$(RUN_ID)

xsweep-all:
	. .venv/bin/activate && $(PY) scripts/xsweep_all.py --glob "$(CONFIG_GLOB)" --seeds "$(SEEDS)" --trials $(TRIALS) --mode $(MODE) --outdir "$(RUN_DIR)"
	printf "%s\n" "$(RUN_ID)" > $(RUN_CURRENT)

topn:
	$(PY) scripts/update_readme_topn.py

aggregate: ## Aggregate per-run CSV/notes into results/<RUN_DIR>
	if [ -x "$(PY)" ]; then \
		"$(PY)" scripts/aggregate_results.py --outdir "$(RUN_DIR)"; \
	else \
		python scripts/aggregate_results.py --outdir "$(RUN_DIR)"; \
	fi

plot: ## Plot results (safe wrapper creates placeholder SVG if empty)
	# Use safe wrapper which writes a placeholder SVG if no data or plot fails
	if [ -f "$(VENV)/bin/activate" ]; then \
		. "$(VENV)/bin/activate" && python tools/plot_safe.py --outdir "$(RUN_DIR)"; \
	else \
		python tools/plot_safe.py --outdir "$(RUN_DIR)"; \
	fi

# --- Testing shortcuts -------------------------------------------------------
.PHONY: test-unit
test-unit: install ## Run fast unit tests only
	@$(PY) -m pytest -q tests/test_paths.py

.PHONY: test
test: install ## Run all Python tests
	$(MAKE) demo RUN_ID=$(RUN_ID)
	printf "%s\n" "$(RUN_ID)" > $(RUN_CURRENT)
	@$(PY) -m pytest -q

notes: ## Auto-generate run notes if script is available
	if [ -x "$(PY)" ]; then \
		"$(PY)" scripts/aggregate_results.py --outdir "$(RUN_DIR)"; \
	else \
		python scripts/aggregate_results.py --outdir "$(RUN_DIR)"; \
	fi

report: aggregate plot notes latest ## Publish artifacts to results/ and refresh LATEST
	mkdir -p $(RESULTS_DIR)
	# Apply schema v1: add 'schema' column to summary.csv and write run.json
	python tools/apply_schema_v1.py "$(RUN_DIR)"
	cp -f "$(RUN_DIR)/summary.csv" $(RESULTS_DIR)/summary.csv
	cp -f "$(RUN_DIR)/summary.svg" $(RESULTS_DIR)/summary.svg
	cp -f "$(RUN_DIR)/summary.md" $(RESULTS_DIR)/summary.md
	cp -f "$(RUN_DIR)/notes.md" $(RESULTS_DIR)/notes.md 2>/dev/null || true
	cp -f "$(RUN_DIR)/run.json" $(RESULTS_DIR)/run.json 2>/dev/null || true
	# Generate per-run HTML report + mirror to LATEST
	python tools/mk_report.py "$(RUN_DIR)"
	if [ -e "$(RESULTS_DIR)/LATEST" ] || [ -L "$(RESULTS_DIR)/LATEST" ] || [ -f "$(RESULTS_DIR)/LATEST.path" ]; then \
		python tools/mk_report.py "$(RESULTS_DIR)/LATEST"; \
	fi
	rm -f $(RUN_CURRENT)
	if [ -x "$(PY)" ]; then \
		"$(PY)" scripts/update_readme_results.py; \
		"$(PY)" scripts/update_readme_topn.py; \
	else \
		python scripts/update_readme_results.py; \
		python scripts/update_readme_topn.py; \
	fi

real1:
	$(MAKE) run SEED=42 TRIALS=5 MODE=REAL

scaffold:
	mkdir -p adapters attacks defenses filters configs/airline_escalating_v1 $(RESULTS_DIR) analysis

.PHONY: journal
journal: install
	$(PY) scripts/new_journal_entry.py

.PHONY: install-tau
install-tau: install
	$(PY) scripts/ensure_tau_bench.py || (echo "tau_bench unavailable; continuing without real τ-Bench" && exit 0)

.PHONY: ci
ci: install ## CI entrypoint: minimal sweep & report (used in smoke)
	$(MAKE) xsweep MODE=SHIM TRIALS=3 SEEDS=41,42 RUN_ID=$(RUN_ID)
	$(MAKE) report RUN_ID=$(RUN_ID)

.PHONY: latest
latest:
	@$(PYTHON) tools/latest_run.py $(RESULTS_DIR) $(LATEST_LINK) || true

tidy-run: ## Remove redundant files in results/$(RUN_ID) (timestamped copies, PNG)
	@d="results/$(RUN_ID)"; \
	if [ -d "$$d" ]; then \
	  rm -f "$$d"/index_* "$$d"/summary_*.csv "$$d"/summary_*.svg "$$d"/summary_*.md "$$d"/run_*.json "$$d"/summary.png 2>/dev/null || true; \
	  echo "Tidied $$d"; \
	else \
	  echo "No run dir at $$d"; \
	fi

open-artifacts: latest
	@$(PYTHON) tools/open_artifacts.py --results "$(RESULTS_DIR)/LATEST"

#
# === Provider probes ===
.PHONY: probe-groq
probe-groq: ## Verify Groq connectivity (needs GROQ_API_KEY)
	@$(PYTHON) tools/llm_probe.py --provider groq --model llama-3.1-8b-instant --prompt "Say: OK"

.PHONY: probe-gemini
probe-gemini: ## Verify Gemini connectivity (needs GEMINI_API_KEY)
	@$(PYTHON) tools/llm_probe.py --provider gemini --model gemini-1.5-flash-latest --prompt "Say: OK"

.PHONY: env-example
env-example: ## Write a local .env from template if missing
	@[ -f .env ] && echo ".env already exists" || (cp .env.example .env && echo "Wrote .env (fill in keys)")

.PHONY: list-runs
list-runs: ## List timestamped results/<RUN_ID> folders and whether CSV/SVG exist
	@if [ ! -d "$(RESULTS_DIR)" ]; then \
		printf "No runs found in %s\n" "$(RESULTS_DIR)"; \
	else \
		printf "%-35s  %-3s  %-3s  %-5s %s\n" "RUN_DIR" "CSV" "SVG" "NOTES" "SIZE"; \
                find "$(RESULTS_DIR)" -mindepth 1 -maxdepth 1 -type d -name "20*" | sort | while read -r d; do \
                        test -f "$$d/summary.csv" && c=✓ || c=×; \
                        test -f "$$d/summary.svg" && s=✓ || s=×; \
                        test -f "$$d/notes.md" && n=✓ || n=×; \
                        sz=$$(du -sh "$$d" 2>/dev/null | cut -f1); \
                        [ -n "$$sz" ] || sz=-; \
                        printf "%-35s  %-3s  %-3s  %-5s %s\n" "$${d#$(RESULTS_DIR)/}" "$$c" "$$s" "$$n" "$$sz"; \
                done; \
        fi

.PHONY: help
help: ## List common targets and brief docs
	@echo "DoomArena-Lab — common targets:"; \
	grep -E '^[a-zA-Z0-9_-]+:.*?## ' $(firstword $(MAKEFILE_LIST)) | sed 's/:.*## / — /' | sort

.PHONY: vars
vars: ## Print effective overridable variables
	@echo "EXP=$(EXP)"; \
	echo "TRIALS=$(TRIALS)"; \
	echo "SEED=$(SEED)"; \
	echo "SEEDS=$(SEEDS)"; \
	echo "MODE=$(MODE)"; \
	echo "RUN_ID=$(RUN_ID)"; \
	echo "RESULTS_DIR=$(RESULTS_DIR)"

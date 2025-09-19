.PHONY: venv install test run sweep aggregate report scaffold check-schema plot notes sweep3 real1 xrun xsweep xsweep-all topn demo test-unit

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

venv: ## Create local virtualenv
	python -m venv $(VENV)
	$(PY) -m pip install -U pip

install: venv ## Install runtime + dev deps into .venv
	$(PIP) install -U doomarena doomarena-taubench pytest pyyaml pandas matplotlib
	$(PY) scripts/ensure_tau_bench.py || (echo "tau_bench unavailable; continuing without real τ-Bench" && exit 0)

check-schema: venv
	$(PY) scripts/check_schema.py

run: install ## Run single experiment (uses CONFIG/EXP defaults)
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

sweep: install ## Multi-seed sweep
	. .venv/bin/activate && python scripts/run_batch.py --exp $(EXP) --seeds "$(SEEDS)" --trials $(TRIALS) --mode $(MODE) --outdir "$(RUN_DIR)"
	printf "%s\n" "$(RUN_ID)" > $(RUN_CURRENT)
	$(MAKE) report RUN_ID=$(RUN_ID)

.PHONY: demo
demo: install ## Tiny SHIM sweep to produce minimal artifacts
	$(MAKE) xsweep CONFIG=configs/airline_escalating_v1/run.yaml EXP=airline_escalating_v1 TRIALS=3 SEEDS="11,12" MODE=SHIM RUN_ID=$(RUN_ID)
	$(MAKE) xsweep CONFIG=configs/airline_static_v1/run.yaml     EXP=airline_static_v1     TRIALS=3 SEEDS="11,12" MODE=SHIM RUN_ID=$(RUN_ID)
	$(MAKE) report RUN_ID=$(RUN_ID)

.ONESHELL: xsweep
xsweep: install ## Configurable sweep (uses CONFIG)
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

aggregate:
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

notes:
	if [ -x "$(PY)" ]; then \
		"$(PY)" scripts/aggregate_results.py --outdir "$(RUN_DIR)"; \
	else \
		python scripts/aggregate_results.py --outdir "$(RUN_DIR)"; \
	fi

report: aggregate plot notes latest
	mkdir -p $(RESULTS_DIR)
	# Apply schema v1: add 'schema' column to summary.csv and write run.json
	python tools/apply_schema_v1.py "$(RUN_DIR)"
	cp -f "$(RUN_DIR)/summary.csv" $(RESULTS_DIR)/summary.csv
	cp -f "$(RUN_DIR)/summary.svg" $(RESULTS_DIR)/summary.svg
	cp -f "$(RUN_DIR)/summary.md" $(RESULTS_DIR)/summary.md
	cp -f "$(RUN_DIR)/notes.md" $(RESULTS_DIR)/notes.md 2>/dev/null || true
	cp -f "$(RUN_DIR)/run.json" $(RESULTS_DIR)/run.json 2>/dev/null || true
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
ci: install
	$(MAKE) xsweep MODE=SHIM TRIALS=3 SEEDS=41,42 RUN_ID=$(RUN_ID)
	$(MAKE) report RUN_ID=$(RUN_ID)

.PHONY: latest
latest:
	@$(PYTHON) tools/latest_run.py $(RESULTS_DIR) $(LATEST_LINK) || true

.PHONY: open-artifacts
open-artifacts: latest
	@$(PYTHON) tools/open_artifacts.py

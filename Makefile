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

.PHONY: venv install test run sweep aggregate report scaffold check-schema plot notes sweep3 real1 xrun xsweep xsweep-all topn demo test-unit ci latest tidy-run open-artifacts open-report list-runs journal install-tau help vars check-thresholds mvp validate

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
STREAM ?= 0

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
	$(PIP) install -U doomarena doomarena-taubench pytest pyyaml jsonschema pandas matplotlib
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

.ONESHELL: real-escalating
.PHONY: real-escalating ## REAL MVP: run airline_escalating_v1 on Groq and publish report
real-escalating:
	@echo "== REAL airline_escalating_v1 =="
	@mkdir -p "$(RUN_DIR)"
	@if [ -x "$(PY)" ]; then PYBIN="$(PY)"; else PYBIN="python3"; fi
	@REAL_MODEL_VALUE="$${REAL_MODEL:-llama-3.1-8b-instant}"
	@$$PYBIN scripts/experiments/airline_escalating_real.py --exp airline_escalating_v1 --seeds "$(SEEDS)" --trials $(TRIALS) --model "$$REAL_MODEL_VALUE" --outdir "$(RUN_DIR)"
	@$(MAKE) report RUN_ID=$(RUN_ID)

.ONESHELL: real-tau-risky
.PHONY: real-tau-risky ## REAL: τ-Bench risky slice via Groq → report
real-tau-risky:
	@echo "== REAL τ-Bench risky slice =="
	@mkdir -p "$(RUN_DIR)"
	@if [ -x "$(PY)" ]; then PYBIN="$(PY)"; else PYBIN="python3"; fi; \
	$$PYBIN scripts/experiments/tau_risky_real.py --exp tau_risky_v1 --seeds "$(SEEDS)" --trials $(TRIALS) --model "$${REAL_MODEL:-llama-3.1-8b-instant}" --outdir "$(RUN_DIR)" --risk "$${RISK_TYPE:-pii_exfiltration}"
	@$(MAKE) report RUN_ID=$(RUN_ID)

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
		"$(PY)" scripts/aggregate_results.py --outdir "$(RUN_DIR)" --emit-status=always; \
	else \
		python scripts/aggregate_results.py --outdir "$(RUN_DIR)" --emit-status=always; \
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
		"$(PY)" scripts/aggregate_results.py --outdir "$(RUN_DIR)" --emit-status=never; \
	else \
		python scripts/aggregate_results.py --outdir "$(RUN_DIR)" --emit-status=never; \
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
	cp -f "$(RUN_DIR)/run_report.json" $(RESULTS_DIR)/run_report.json 2>/dev/null || true
	# Generate per-run HTML report + mirror to LATEST
        python -m tools.report.html_report "$(RUN_DIR)"
        if [ -e "$(RESULTS_DIR)/LATEST" ] || [ -L "$(RESULTS_DIR)/LATEST" ] || [ -f "$(RESULTS_DIR)/LATEST.path" ]; then \
                python -m tools.report.html_report "$(RESULTS_DIR)/LATEST"; \
        fi
	rm -f $(RUN_CURRENT)
	if [ -x "$(PY)" ]; then \
	"$(PY)" scripts/update_readme_results.py; \
	"$(PY)" scripts/update_readme_topn.py; \
	else \
	python scripts/update_readme_results.py; \
	python scripts/update_readme_topn.py; \
	fi

.PHONY: check-thresholds
check-thresholds: ## Evaluate aggregated metrics against thresholds.yaml
	@set -euo pipefail; \
	PYBIN="$(PYTHON)"; \
	if [ -x "$(PY)" ]; then PYBIN="$(PY)"; fi; \
	RID="$(RUN_ID)"; \
	if [ -n "$$RID" ] && [ ! -d "$(RESULTS_DIR)/$$RID" ]; then RID=""; fi; \
	if [ -z "$$RID" ] && [ -f "$(RESULTS_DIR)/.run_id" ]; then RID="$$(cat $(RESULTS_DIR)/.run_id)"; fi; \
	CMD="\"$$PYBIN\" tools/check_thresholds.py --results-root \"$(RESULTS_DIR)\" --thresholds \"thresholds.yaml\""; \
	STRICT_VALUE="$(STRICT)"; \
	case "$$STRICT_VALUE" in \
	1|true|TRUE|True|yes|YES|on|ON) CMD="$$CMD --strict";; \
	esac; \
	if [ -n "$$RID" ]; then \
	CMD="RUN_ID=\"$$RID\" $$CMD"; \
	fi; \
	eval "$$CMD"

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
	@if $(PYTHON) tools/latest_run.py $(RESULTS_DIR) $(LATEST_LINK); then \
		: ; \
	else \
		echo "ERROR: failed to update results/LATEST; see logs" >&2; \
		exit 1; \
	fi

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

.ONESHELL: mvp
mvp: ## Translator → REAL slice → aggregate + refresh LATEST (dry-run by default)
	@set -euo pipefail
	if [ -f .env ]; then
		set -a
		. ./.env
		set +a
	fi
	MODEL_VALUE="$${MODEL:-llama-3.1-8b-instant}"
	TRIALS_VALUE="$${TRIALS:-3}"
	SEED_VALUE="$${SEED:-42}"
	DRY_RAW="$${DRY_RUN:-1}"
	RUN_ID_VALUE="$${RUN_ID:-$(RUN_ID)}"
	DRY_FLAG=""
	DRY_CANON="0"
	case "$$DRY_RAW" in
	1|true|TRUE|True|yes|YES|on|ON) DRY_FLAG="--dry-run"; DRY_CANON="1" ;;
	esac
	STREAM_RAW="$${STREAM:-0}"
	STREAM_FLAG=""
	case "$$STREAM_RAW" in
	1|true|TRUE|True|yes|YES|on|ON) STREAM_FLAG="--stream" ;;
	esac
	export MODEL="$$MODEL_VALUE" TRIALS="$$TRIALS_VALUE" SEED="$$SEED_VALUE" DRY_RUN="$$DRY_RAW" RUN_ID="$$RUN_ID_VALUE"
	if [ "$$DRY_CANON" = "1" ] && [ -z "$${GROQ_API_KEY:-}" ]; then
		export GROQ_API_KEY="stub-dry-run-key"
	fi
	if [ "$$DRY_CANON" != "1" ] && [ -z "$${GROQ_API_KEY:-}" ]; then
		echo "ERROR: GROQ_API_KEY is required for real runs (set it in .env or the environment)." >&2
		exit 2
	fi
	if [ -f specs/threat_model.yaml ]; then
		echo "== Translating specs/threat_model.yaml =="
		if [ -n "$${MVP_TRANSLATE_CMD:-}" ]; then
			eval "$${MVP_TRANSLATE_CMD}"
		else
			translator_ran=0
			for candidate in scripts/translate_threat_model.py tools/translate_threat_model.py scripts/threat_model_to_cases.py tools/threat_model_to_cases.py scripts/translator.py tools/translator.py; do
				if [ -f "$$candidate" ]; then
					$(PYTHON) "$$candidate" --input specs/threat_model.yaml
					translator_ran=1
					break
				fi
				done
			if [ "$$translator_ran" -eq 0 ]; then
				echo "ERROR: specs/threat_model.yaml present but no translator script found. Set MVP_TRANSLATE_CMD to override." >&2
				exit 3
			fi
		fi
	fi
	echo "== Running REAL slice (seed=$$SEED_VALUE trials=$$TRIALS_VALUE model=$$MODEL_VALUE dry_run=$$DRY_CANON) =="
	$(PYTHON) -m scripts.experiments.tau_risky_real --model "$$MODEL_VALUE" --trials "$$TRIALS_VALUE" --seed "$$SEED_VALUE" $$DRY_FLAG
	RUN_ROOT="$(RESULTS_DIR)/$$RUN_ID_VALUE"
	echo "== Aggregating results in $$RUN_ROOT =="
	$(PYTHON) -m scripts.aggregate_results --outdir "$$RUN_ROOT" $$STREAM_FLAG --emit-status=always
	$(PYTHON) tools/apply_schema_v1.py "$$RUN_ROOT"
	$(PYTHON) tools/plot_safe.py --outdir "$$RUN_ROOT"
        $(PYTHON) -m tools.report.html_report "$$RUN_ROOT"
	$(PYTHON) tools/latest_run.py "$(RESULTS_DIR)" "$(LATEST_LINK)"
        if [ -e "$(LATEST_LINK)" ] || [ -L "$(LATEST_LINK)" ]; then
                $(PYTHON) -m tools.report.html_report "$(LATEST_LINK)"
	fi
	ROWS_WRITTEN="$$(RUN_ID="$$RUN_ID_VALUE" $(PYTHON) - <<-'PY'
	import os
	from pathlib import Path
	
	run_id = os.environ.get("RUN_ID", "")
	rows_path = Path("$(RESULTS_DIR)") / run_id / "tau_risky_real" / "rows.jsonl"
	print(sum(1 for line in rows_path.read_text(encoding="utf-8").splitlines() if line.strip()) if rows_path.exists() else 0)
	PY
	)"
	INDEX_PATH="$$(RUN_ID="$$RUN_ID_VALUE" $(PYTHON) - <<-'PY'
	import os
	from pathlib import Path
	
	run_id = os.environ.get("RUN_ID", "")
	index_path = Path("$(RESULTS_DIR)") / run_id / "index.html"
	print(index_path.resolve())
	PY
	)"
	echo "MVP complete: run_id=$$RUN_ID_VALUE rows=$$ROWS_WRITTEN index=$$INDEX_PATH"

.PHONY: open-report
open-report: ## Open results/LATEST/index.html locally (prints path in CI)
	@set -euo pipefail
	$(PYTHON) tools/open_report.py "$(RESULTS_DIR)/LATEST"

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
validate: ## Validate configuration files (YAML → JSON Schema)
	@if [ -x "$(PY)" ]; then PYBIN="$(PY)"; else PYBIN="$(PYTHON)"; fi; \
	"$$PYBIN" tools/ci_preflight.py


.PHONY: venv install test run sweep aggregate report scaffold check-schema plot sweep3 real1 xrun xsweep xsweep-all topn

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

venv:
	python -m venv $(VENV)
	$(PY) -m pip install -U pip

install: venv
	$(PIP) install -U doomarena doomarena-taubench pytest pyyaml pandas matplotlib
	$(PY) scripts/ensure_tau_bench.py || (echo "tau_bench unavailable; continuing without real τ-Bench" && exit 0)

test: install
	$(PY) -m pytest -q

check-schema: venv
	$(PY) scripts/check_schema.py

run:
	. .venv/bin/activate && python scripts/run_batch.py --exp $(EXP) --seeds "$(SEED)" --trials $(TRIALS) --mode $(MODE)

xrun:
	. .venv/bin/activate && python scripts/run_experiment.py --config $(CONFIG) --seed $(SEED)

sweep:
	. .venv/bin/activate && python scripts/run_batch.py --exp $(EXP) --seeds "$(SEEDS)" --trials $(TRIALS) --mode $(MODE)
	$(MAKE) report

.ONESHELL: xsweep
xsweep:
	if [ -x "$(PY)" ]; then PYTHON_BIN="$(PY)"; else PYTHON_BIN="python"; fi; \
	CONFIG_PATH="$(CONFIG)" MODE_OVERRIDE="$(MODE_OVERRIDE)" TRIALS_OVERRIDE="$(TRIALS_OVERRIDE)" SEEDS_OVERRIDE="$(SEEDS_OVERRIDE)" EXP_OVERRIDE="$(EXP)" "$${PYTHON_BIN}" - <<-'PY'
	import os
	import shlex
	import subprocess
	import sys
	
	cmd = [sys.executable, "scripts/xsweep.py", "--config", os.environ["CONFIG_PATH"]]
	seeds_override = os.environ.get("SEEDS_OVERRIDE", "").strip()
	if seeds_override: cmd.extend(["--seeds", seeds_override])
	mode_override = os.environ.get("MODE_OVERRIDE", "").strip()
	if mode_override: cmd.extend(["--mode", mode_override])
	trials_override = os.environ.get("TRIALS_OVERRIDE", "").strip()
	if trials_override: cmd.extend(["--trials", trials_override])
	exp_override = os.environ.get("EXP_OVERRIDE", "").strip()
	if exp_override: cmd.extend(["--exp", exp_override])
	
	print("xsweep:", " ".join(shlex.quote(part) for part in cmd))
	sys.exit(subprocess.call(cmd))
	PY

sweep3:
	$(MAKE) sweep SEEDS="41,42,43" TRIALS=5 MODE=SHIM

xsweep-all:
	. .venv/bin/activate && $(PY) scripts/xsweep_all.py --glob "$(CONFIG_GLOB)" --seeds "$(SEEDS)" --trials $(TRIALS) --mode $(MODE)

topn:
	$(PY) scripts/update_readme_topn.py

aggregate:
		if [ -x "$(PY)" ]; then \
		"$(PY)" scripts/aggregate_results.py; \
	else \
		python scripts/aggregate_results.py; \
	fi

plot:
	if [ -f "$(VENV)/bin/activate" ]; then \
		. "$(VENV)/bin/activate" && python scripts/plot_results.py --exp $(EXP); \
	else \
		python scripts/plot_results.py --exp $(EXP); \
	fi

report: aggregate plot
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
	mkdir -p adapters attacks defenses filters configs/airline_escalating_v1 results analysis

.PHONY: journal
journal: install
	$(PY) scripts/new_journal_entry.py

.PHONY: install-tau
install-tau: install
	$(PY) scripts/ensure_tau_bench.py || (echo "tau_bench unavailable; continuing without real τ-Bench" && exit 0)

.PHONY: ci
ci:
	$(MAKE) xsweep MODE=SHIM TRIALS=3 SEEDS=41,42
	$(MAKE) report

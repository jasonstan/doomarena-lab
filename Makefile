.PHONY: venv install test run sweep aggregate report scaffold check-schema plot sweep3 real1

VENV := .venv
PY   := $(VENV)/bin/python
PIP  := $(VENV)/bin/pip
CONFIG ?= configs/airline_escalating_v1/run.yaml
SEED ?= 42
SEEDS ?= 41,42,43
TRIALS ?= 5
EXP ?= airline_escalating_v1
MODE ?= SHIM

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

sweep:
	. .venv/bin/activate && python scripts/run_batch.py --exp $(EXP) --seeds "$(SEEDS)" --trials $(TRIALS) --mode $(MODE)
	$(MAKE) report

.ONESHELL: xsweep
xsweep:
	. .venv/bin/activate && python - <<-'PY'
	import subprocess, sys, yaml
	cfg = yaml.safe_load(open("$(CONFIG)", "r"), encoding="utf-8") or {}
	seeds = cfg.get("seeds", [])
	rc = 0
	for s in seeds:
	    rc |= subprocess.call([
	        "bash", "-lc",
	        ". .venv/bin/activate && python scripts/run_experiment.py --config $(CONFIG) --seed %d" % s,
	    ])
	sys.exit(rc)
	PY

sweep3:
	$(MAKE) sweep SEEDS="41,42,43" TRIALS=5 MODE=SHIM

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

# plot stays as-is above…

report: aggregate plot
	if [ -x "$(PY)" ]; then \
		"$(PY)" scripts/update_readme_results.py; \
	else \
		python scripts/update_readme_results.py; \
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

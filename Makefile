.PHONY: venv install test run sweep aggregate report scaffold check-schema

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
	$(PIP) install -U doomarena doomarena-taubench pytest pyyaml pandas
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

aggregate:
	$(PY) scripts/aggregate_results.py

report: aggregate
	$(PY) scripts/update_readme_results.py

scaffold:
	mkdir -p adapters attacks defenses filters configs/airline_escalating_v1 results analysis

.PHONY: journal
journal: install
	$(PY) scripts/new_journal_entry.py

.PHONY: install-tau
install-tau: install
	$(PY) scripts/ensure_tau_bench.py || (echo "tau_bench unavailable; continuing without real τ-Bench" && exit 0)

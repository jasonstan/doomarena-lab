.PHONY: venv install test run aggregate report scaffold

VENV := .venv
PY   := $(VENV)/bin/python
PIP  := $(VENV)/bin/pip
CONFIG ?= configs/airline_escalating_v1/run.yaml

venv:
	python -m venv $(VENV)
	$(PY) -m pip install -U pip

install: venv
	$(PIP) install -U doomarena doomarena-taubench pytest pyyaml pandas
	$(PY) scripts/ensure_tau_bench.py || (echo "tau_bench unavailable; continuing without real τ-Bench" && exit 0)

test: install
	$(PY) -m pytest -q

run: install
	@if [ ! -f scripts/taubench_airline_da.py ]; then \
	  echo "scripts/taubench_airline_da.py not found in this PR. Merge the engine-v2 PR (adds the runner) or create the script."; \
	  exit 1; \
	fi
	$(PY) scripts/taubench_airline_da.py --config $(CONFIG)

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

.ONESHELL:
PY=python
TEST?=-q
CONFIG?=configs/airline_escalating_v1/run.yaml

venv:
	$(PY) -m venv .venv && . .venv/bin/activate && pip install -U pip

install:
	. .venv/bin/activate && pip install -U doomarena doomarena-taubench pytest pyyaml

test:
	. .venv/bin/activate && pytest $(TEST)

run:
	. .venv/bin/activate && $(PY) scripts/taubench_airline_da.py --config $(CONFIG)

scaffold:
	mkdir -p adapters attacks defenses filters configs/airline_escalating_v1 results analysis

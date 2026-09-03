.PHONY: setup seed run run-api run-worker run-simulator run-ui test test-agent verify-strands demo-check demo-rehearsal verify frontend-build secret-scan clean-data

PYTHON ?= .venv/bin/python
PIP ?= .venv/bin/pip

setup:
	python3 -m venv .venv
	$(PIP) install -e '.[dev]'
	npm --prefix frontend install

seed:
	$(PYTHON) -m backend.app.seed.demo

run:
	$(PYTHON) scripts/run_local.py

run-api:
	$(PYTHON) -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload

run-worker:
	$(PYTHON) -m backend.app.scheduling.local_worker

run-simulator:
	$(PYTHON) -m backend.app.scheduling.local_simulator

run-ui:
	npm --prefix frontend run dev

test:
	$(PYTHON) -m pytest
	npm --prefix frontend test

test-agent:
	$(PYTHON) -m pytest tests/unit/test_agents.py

verify-strands:
	$(PYTHON) scripts/verify_strands.py

demo-check:
	$(PYTHON) scripts/demo_check.py

demo-rehearsal:
	$(PYTHON) scripts/demo_check.py --runs $${RUNS:-3}

frontend-build:
	npm --prefix frontend run build

secret-scan:
	$(PYTHON) scripts/secret_scan.py

verify: test frontend-build demo-check secret-scan

clean-data:
	rm -f data/buildingops.db data/buildingops.db-shm data/buildingops.db-wal

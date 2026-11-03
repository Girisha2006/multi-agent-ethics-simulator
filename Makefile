PY ?= .venv/bin/python

.PHONY: install run test evaluate

install:
	python3 -m venv .venv
	$(PY) -m pip install --quiet -r requirements-dev.txt

run:
	./start.sh

test:
	$(PY) -m pytest -q tests

evaluate:
	$(PY) tools/run_evaluation.py

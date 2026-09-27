# Convenience targets for macOS / Linux. Windows users can run the equivalent
# python commands directly (see README) or use `python build.py`.

PYTHON ?= python3

.PHONY: install run test build check clean

install:
	$(PYTHON) -m pip install -r requirements.txt

run:
	$(PYTHON) app.py

test:
	$(PYTHON) tests/smoke_test.py

check:
	$(PYTHON) build.py --check

build:
	$(PYTHON) build.py

clean:
	rm -rf build dist
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +

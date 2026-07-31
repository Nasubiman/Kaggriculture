PYTHON ?= python3.12
VENV := .venv
KAGGLE := $(VENV)/bin/kaggle
COMPETITION := kaggriculture

.PHONY: setup kaggle-check kaggle-download history-collect history-analyze cow-analyze cow-diagnose cow-search evaluate head-to-head

setup:
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/python -m pip install -r requirements.txt

kaggle-check:
	$(KAGGLE) competitions list -s $(COMPETITION)
	$(KAGGLE) competitions files $(COMPETITION)

kaggle-download:
	mkdir -p kaggle-data
	$(KAGGLE) competitions download $(COMPETITION) -p kaggle-data

history-collect:
	$(VENV)/bin/python scripts/collect_public_history.py

history-analyze:
	$(VENV)/bin/python scripts/analyze_public_history.py

cow-analyze:
	$(VENV)/bin/python scripts/analyze_cow_strategy.py

cow-diagnose:
	$(VENV)/bin/python scripts/diagnose_cow_candidate.py

cow-search:
	$(VENV)/bin/python scripts/search_cow_variants.py

evaluate:
	$(VENV)/bin/python scripts/evaluate_agent.py

head-to-head:
	$(VENV)/bin/python scripts/head_to_head.py

PYTHON ?= python3.12
VENV := .venv
KAGGLE := $(VENV)/bin/kaggle
COMPETITION := kaggriculture
SERVER_HOST ?= kag-server
SERVER_REPO ?= /home/nakamura_y/agriculture/Kaggriculture
SERVER_DATA ?= /media/deepstation/storage/nakamura_y/kaggriculture
SERVER_REFERENCE ?= $(SERVER_DATA)/datasets/reference/score800_reference.txt
SERVER_RESULTS ?= server-results

.PHONY: setup kaggle-check kaggle-download history-collect history-analyze cow-analyze cow-diagnose cow-search evaluate head-to-head server-check server-update-code server-evaluate server-head-to-head server-push-replays server-push-datasets server-pull-results

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

server-check:
	ssh $(SERVER_HOST) 'set -eu; cd "$(SERVER_REPO)"; printf "repo=%s\n" "$$PWD"; .venv/bin/python --version; git status --short; nvidia-smi --query-gpu=index,name,memory.total --format=csv,noheader; df -h "$(SERVER_DATA)"'

server-update-code:
	test -z "$$(git status --porcelain)"
	git push $(SERVER_HOST):$(SERVER_REPO) HEAD:main

server-evaluate:
	ssh $(SERVER_HOST) 'set -eu; cd "$(SERVER_REPO)"; mkdir -p "$(SERVER_DATA)/runs/manual"; .venv/bin/python scripts/evaluate_agent.py --output "$(SERVER_DATA)/runs/manual/baseline_evaluation.json"'

server-head-to-head:
	ssh $(SERVER_HOST) 'set -eu; cd "$(SERVER_REPO)"; mkdir -p "$(SERVER_DATA)/runs/manual"; .venv/bin/python scripts/head_to_head.py --reference "$(SERVER_REFERENCE)" --seeds 7101 7102 7103 7104 7105 --output "$(SERVER_DATA)/runs/manual/cow_vs_score800.json"'

server-push-replays:
	test -d replays
	ssh $(SERVER_HOST) 'mkdir -p "$(SERVER_DATA)/datasets/replays"'
	rsync -avz --progress replays/ $(SERVER_HOST):$(SERVER_DATA)/datasets/replays/

server-push-datasets:
	test -d datasets/processed
	ssh $(SERVER_HOST) 'mkdir -p "$(SERVER_DATA)/datasets/processed"'
	rsync -avz --progress datasets/processed/ $(SERVER_HOST):$(SERVER_DATA)/datasets/processed/

server-pull-results:
	mkdir -p $(SERVER_RESULTS)
	rsync -avz --progress $(SERVER_HOST):$(SERVER_DATA)/runs/ $(SERVER_RESULTS)/

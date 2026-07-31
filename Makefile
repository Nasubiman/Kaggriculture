PYTHON ?= python3.12
VENV := .venv
KAGGLE := $(VENV)/bin/kaggle
COMPETITION := kaggriculture
SERVER_HOST ?= kag-server
SERVER_REPO ?= /home/nakamura_y/agriculture/Kaggriculture
SERVER_DATA ?= /media/deepstation/storage/nakamura_y/kaggriculture
SERVER_REFERENCE ?= $(SERVER_DATA)/datasets/reference/score800_reference.txt
SERVER_RESULTS ?= server-results
HYBRID_RUN ?= $(SERVER_DATA)/runs/hybrid_ppo_manual
HYBRID_ITERATIONS ?= 20
HYBRID_GAMES ?= 60
HYBRID_WORKERS ?= 20
CF_DATA ?= $(SERVER_DATA)/datasets/counterfactual/branched_multiday_manual.json
CF_RUN ?= $(SERVER_DATA)/runs/counterfactual_value_manual
CF_SEEDS ?= 200
CF_PROFILES ?= KEEP COW_14 COW_15 SHEEP_2 SHEEP_3 HANDS_10 WHEAT_4 BATCH_6
CF_DECISION_DAY ?= 8

.PHONY: setup kaggle-check kaggle-download history-collect history-analyze cow-analyze cow-diagnose cow-search evaluate head-to-head server-check server-gpu-check server-update-code server-evaluate server-head-to-head server-hybrid-train server-counterfactual-generate server-counterfactual-train server-counterfactual-evaluate server-push-replays server-push-datasets server-pull-results

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

server-gpu-check:
	ssh $(SERVER_HOST) 'set -eu; cd "$(SERVER_REPO)"; .venv/bin/python -c "import torch; print({\"torch\": torch.__version__, \"cuda\": torch.version.cuda, \"available\": torch.cuda.is_available(), \"devices\": [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]})"'

server-update-code:
	test -z "$$(git status --porcelain)"
	git push $(SERVER_HOST):$(SERVER_REPO) HEAD:main

server-evaluate:
	ssh $(SERVER_HOST) 'set -eu; cd "$(SERVER_REPO)"; mkdir -p "$(SERVER_DATA)/runs/manual"; .venv/bin/python scripts/evaluate_agent.py --output "$(SERVER_DATA)/runs/manual/baseline_evaluation.json"'

server-head-to-head:
	ssh $(SERVER_HOST) 'set -eu; cd "$(SERVER_REPO)"; mkdir -p "$(SERVER_DATA)/runs/manual"; .venv/bin/python scripts/head_to_head.py --reference "$(SERVER_REFERENCE)" --seeds 7101 7102 7103 7104 7105 --output "$(SERVER_DATA)/runs/manual/cow_vs_score800.json"'

server-hybrid-train:
	ssh $(SERVER_HOST) 'set -eu; cd "$(SERVER_REPO)"; mkdir -p "$(HYBRID_RUN)"; OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=0 .venv/bin/python training/train_hybrid_ppo.py --output-dir "$(HYBRID_RUN)" --iterations "$(HYBRID_ITERATIONS)" --games-per-iteration "$(HYBRID_GAMES)" --workers "$(HYBRID_WORKERS)" --score800-reference "$(SERVER_REFERENCE)" --device cuda'

server-counterfactual-generate:
	ssh $(SERVER_HOST) 'set -eu; cd "$(SERVER_REPO)"; mkdir -p "$$(dirname "$(CF_DATA)")"; OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/bin/python training/generate_branched_counterfactuals.py --agent main.py --opponent main.py --decision-days 8 12 16 20 24 --seed-start 1100000 --seeds "$(CF_SEEDS)" --workers 20 --profiles $(CF_PROFILES) --output "$(CF_DATA)"'

server-counterfactual-train:
	ssh $(SERVER_HOST) 'set -eu; cd "$(SERVER_REPO)"; mkdir -p "$(CF_RUN)"; CUDA_VISIBLE_DEVICES=0 .venv/bin/python training/train_counterfactual_value.py --input "$(CF_DATA)" --profiles $(CF_PROFILES) --output-dir "$(CF_RUN)" --epochs 400 --patience 80 --hidden-size 1024 --hidden-layers 6 --batch-size 1024 --device cuda --amp'

server-counterfactual-evaluate:
	ssh $(SERVER_HOST) 'set -eu; cd "$(SERVER_REPO)"; OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/bin/python training/evaluate_counterfactual_value.py --checkpoint "$(CF_RUN)/best.pt" --agent main.py --opponent main.py --decision-day "$(CF_DECISION_DAY)" --seed-start 1200000 --seeds 200 --workers 20 --fast-runner --output "$(CF_RUN)/arena_heldout.json"'

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

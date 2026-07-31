PYTHON ?= python3.12
VENV := .venv
KAGGLE := $(VENV)/bin/kaggle
COMPETITION := kaggriculture
SERVER_HOST ?= kag-server
SERVER_REPO ?= /home/nakamura_y/agriculture/Kaggriculture
SERVER_DATA ?= /media/deepstation/storage/nakamura_y/kaggriculture
SERVER_REFERENCE ?= $(SERVER_DATA)/datasets/reference/score800_reference.txt
SERVER_STRONG_REFERENCE ?= $(SERVER_DATA)/datasets/reference/submission_tar_main.py
SERVER_RESULTS ?= server-results
TEST_DIR ?= test
TEST_MODEL ?=
TEST_MODELS ?=
TEST_SEEDS ?= 100
TEST_WORKERS ?= 20
TEST_OUTPUT ?= reports/test_models.json
HYBRID_RUN ?= $(SERVER_DATA)/runs/hybrid_ppo_manual
HYBRID_ITERATIONS ?= 20
HYBRID_GAMES ?= 60
HYBRID_WORKERS ?= 20
CF_DATA ?= $(SERVER_DATA)/datasets/counterfactual/branched_multiday_manual.json
CF_RUN ?= $(SERVER_DATA)/runs/counterfactual_value_manual
CF_SEEDS ?= 200
CF_PROFILES ?= KEEP COW_14 COW_15 SHEEP_2 SHEEP_3 HANDS_10 WHEAT_4 BATCH_6
CF_DECISION_DAY ?= 8
STRUCTURED_NAME ?= structured_$(shell date +%Y%m%d_%H%M%S)
STRUCTURED_RUN ?= $(SERVER_DATA)/runs/$(STRUCTURED_NAME)
STRUCTURED_LOCAL_RUN ?= $(SERVER_RESULTS)/$(STRUCTURED_NAME)
STRUCTURED_MINUTES ?= 90
STRUCTURED_POPULATION ?= 48
STRUCTURED_WORKERS ?= 20
STRUCTURED_HELDOUT_SEEDS ?= 200
STRUCTURED_PARITY_SEEDS ?= 20
STRUCTURED_GATE_SEEDS ?= 200
LAST_STRUCTURED_RUN := $(SERVER_RESULTS)/LATEST_STRUCTURED_RUN
RUN ?= $(shell test -f "$(LAST_STRUCTURED_RUN)" && cat "$(LAST_STRUCTURED_RUN)")

.PHONY: setup kaggle-check kaggle-download history-collect history-analyze cow-analyze cow-diagnose cow-search evaluate head-to-head test-import test-list test-models server-test-models genome-train genome-status genome-candidate genome-use server-check server-gpu-check server-update-code server-evaluate server-head-to-head server-hybrid-train server-structured-search server-structured-gate server-counterfactual-generate server-counterfactual-train server-counterfactual-evaluate server-push-replays server-push-datasets server-pull-results

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

# Store submission.tar.gz as test/<name>/main.py. Example: make test-import TEST_MODEL=rank1_20260801
test-import:
	test -n "$(TEST_MODEL)"
	$(VENV)/bin/python scripts/import_test_model.py "$(TEST_MODEL)" --archive submission.tar.gz --models-dir "$(TEST_DIR)"

test-list:
	@find "$(TEST_DIR)" -mindepth 2 -maxdepth 2 -name main.py -print 2>/dev/null | sed 's#^$(TEST_DIR)/##; s#/main.py$$##' | sort

# Evaluate main.py against all test models, or TEST_MODELS="name1 name2".
test-models:
	PYTHONPATH=training $(VENV)/bin/python scripts/evaluate_test_models.py --candidate main.py --models-dir "$(TEST_DIR)" $(if $(strip $(TEST_MODELS)),--models $(TEST_MODELS),) --seeds "$(TEST_SEEDS)" --workers "$(TEST_WORKERS)" --output "$(TEST_OUTPUT)"

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

server-test-models:
	test -d "$(TEST_DIR)"
	ssh $(SERVER_HOST) 'mkdir -p "$(SERVER_REPO)/scripts" "$(SERVER_REPO)/training"'
	rsync -az main.py $(SERVER_HOST):$(SERVER_REPO)/main.py
	rsync -az scripts/evaluate_test_models.py $(SERVER_HOST):$(SERVER_REPO)/scripts/
	rsync -az training/fast_kaggriculture.py $(SERVER_HOST):$(SERVER_REPO)/training/
	rsync -az --delete "$(TEST_DIR)/" $(SERVER_HOST):$(SERVER_REPO)/test/
	ssh $(SERVER_HOST) 'set -eu; cd "$(SERVER_REPO)"; mkdir -p "$(SERVER_DATA)/runs/manual"; PYTHONPATH=training .venv/bin/python scripts/evaluate_test_models.py --candidate main.py --models-dir test $(if $(strip $(TEST_MODELS)),--models $(TEST_MODELS),) --seeds "$(TEST_SEEDS)" --workers "$(TEST_WORKERS)" --output "$(SERVER_DATA)/runs/manual/test_models.json"'
	mkdir -p "$(dir $(TEST_OUTPUT))"
	rsync -az $(SERVER_HOST):$(SERVER_DATA)/runs/manual/test_models.json "$(TEST_OUTPUT)"

server-hybrid-train:
	ssh $(SERVER_HOST) 'set -eu; cd "$(SERVER_REPO)"; mkdir -p "$(HYBRID_RUN)"; OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=0 .venv/bin/python training/train_hybrid_ppo.py --output-dir "$(HYBRID_RUN)" --iterations "$(HYBRID_ITERATIONS)" --games-per-iteration "$(HYBRID_GAMES)" --workers "$(HYBRID_WORKERS)" --score800-reference "$(SERVER_REFERENCE)" --device cuda'

server-structured-search:
	ssh $(SERVER_HOST) 'set -eu; cd "$(SERVER_REPO)"; mkdir -p "$(STRUCTURED_RUN)"; OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=0 PYTHONPATH=training .venv/bin/python training/search_structured_strategies.py --minutes "$(STRUCTURED_MINUTES)" --population "$(STRUCTURED_POPULATION)" --proposal-multiplier 96 --stage1 12 --stage2 4 --workers "$(STRUCTURED_WORKERS)" --device cuda --output-dir "$(STRUCTURED_RUN)"'

server-structured-gate:
	ssh $(SERVER_HOST) 'set -eu; cd "$(SERVER_REPO)"; test -f "$(STRUCTURED_RUN)/best_genome.json"; found=0; for opponent in test/*/main.py; do test -f "$$opponent" || continue; found=1; name=$$(basename "$$(dirname "$$opponent")"); PYTHONPATH=training .venv/bin/python training/evaluate_strategy_genome.py --genome "$(STRUCTURED_RUN)/best_genome.json" --opponent "$$opponent" --seed-start 9700000 --seeds "$(STRUCTURED_GATE_SEEDS)" --workers "$(STRUCTURED_WORKERS)" --output "$(STRUCTURED_RUN)/gate_test_$${name}_fast.json"; done; test "$$found" = 1'

# One-command structured search: sync, train, validate, gate, and pull only this run.
genome-train:
	ssh $(SERVER_HOST) 'mkdir -p "$(SERVER_REPO)/training" "$(STRUCTURED_RUN)/source"'
	rsync -az main.py $(SERVER_HOST):$(SERVER_REPO)/main.py
	rsync -az training/strategy_genome.py training/search_structured_strategies.py training/evaluate_strategy_genome.py $(SERVER_HOST):$(SERVER_REPO)/training/
	test -d "$(TEST_DIR)"
	rsync -az --delete "$(TEST_DIR)/" $(SERVER_HOST):$(SERVER_REPO)/test/
	ssh $(SERVER_HOST) 'set -eu; cd "$(SERVER_REPO)"; cp main.py "$(STRUCTURED_RUN)/source/main.py"; cp training/strategy_genome.py training/search_structured_strategies.py training/evaluate_strategy_genome.py "$(STRUCTURED_RUN)/source/"; cp -R test "$(STRUCTURED_RUN)/source/"; git rev-parse HEAD > "$(STRUCTURED_RUN)/source/git_commit.txt"; git diff > "$(STRUCTURED_RUN)/source/worktree.patch"'
	$(MAKE) server-structured-search STRUCTURED_RUN="$(STRUCTURED_RUN)" STRUCTURED_MINUTES="$(STRUCTURED_MINUTES)" STRUCTURED_POPULATION="$(STRUCTURED_POPULATION)" STRUCTURED_WORKERS="$(STRUCTURED_WORKERS)"
	ssh $(SERVER_HOST) 'set -eu; cd "$(SERVER_REPO)"; OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=training .venv/bin/python training/evaluate_strategy_genome.py --genome "$(STRUCTURED_RUN)/best_genome.json" --opponent main.py --seed-start 9800000 --seeds "$(STRUCTURED_HELDOUT_SEEDS)" --workers "$(STRUCTURED_WORKERS)" --fast-runner --output "$(STRUCTURED_RUN)/heldout_vs_current_fast.json"'
	ssh $(SERVER_HOST) 'set -eu; cd "$(SERVER_REPO)"; PYTHONPATH=training .venv/bin/python training/evaluate_strategy_genome.py --genome "$(STRUCTURED_RUN)/best_genome.json" --opponent main.py --seed-start 9900000 --seeds "$(STRUCTURED_PARITY_SEEDS)" --workers "$(STRUCTURED_WORKERS)" --fast-runner --output "$(STRUCTURED_RUN)/parity_fast.json"; PYTHONPATH=training .venv/bin/python training/evaluate_strategy_genome.py --genome "$(STRUCTURED_RUN)/best_genome.json" --opponent main.py --seed-start 9900000 --seeds "$(STRUCTURED_PARITY_SEEDS)" --workers "$(STRUCTURED_WORKERS)" --no-fast-runner --output "$(STRUCTURED_RUN)/parity_standard.json"'
	$(MAKE) server-structured-gate STRUCTURED_RUN="$(STRUCTURED_RUN)" STRUCTURED_GATE_SEEDS="$(STRUCTURED_GATE_SEEDS)" STRUCTURED_WORKERS="$(STRUCTURED_WORKERS)"
	mkdir -p "$(STRUCTURED_LOCAL_RUN)"
	rsync -az --progress $(SERVER_HOST):$(STRUCTURED_RUN)/ "$(STRUCTURED_LOCAL_RUN)/"
	mkdir -p "$(SERVER_RESULTS)"
	printf '%s\n' "$(STRUCTURED_LOCAL_RUN)" > "$(LAST_STRUCTURED_RUN)"
	$(VENV)/bin/python training/summarize_strategy_run.py "$(STRUCTURED_LOCAL_RUN)"
	@printf '\nDone. Next: make genome-candidate\n'

# Show the latest run (or RUN=server-results/...) without opening JSON files.
genome-status:
	test -n "$(RUN)"
	$(VENV)/bin/python training/summarize_strategy_run.py "$(RUN)"

# Build a standalone candidate from the latest run (or RUN=server-results/...).
genome-candidate:
	test -n "$(RUN)"
	test -f "$(RUN)/best_genome.json"
	test -f "$(RUN)/source/main.py"
	$(VENV)/bin/python training/promote_strategy_genome.py --genome "$(RUN)/best_genome.json" --base "$(RUN)/source/main.py" --output candidate_main.py
	$(VENV)/bin/python -m py_compile candidate_main.py
	@printf 'Candidate ready: candidate_main.py\nNext: make genome-use\n'

# Explicitly promote the generated candidate to main.py, keeping one backup in the run.
genome-use: genome-candidate
	test -f "$(RUN)/main_before_promotion.py" || cp main.py "$(RUN)/main_before_promotion.py"
	cp candidate_main.py main.py
	$(VENV)/bin/python -m py_compile main.py
	$(VENV)/bin/python -c 'import main; assert callable(main.agent); print("main.agent OK")'
	cp main.py "$(RUN)/promoted_main.py"
	@printf '\nPromoted %s/best_genome.json to main.py\n' "$(RUN)"

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

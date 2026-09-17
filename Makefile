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
TEST_CANDIDATE ?= main.py
TEST_SEEDS ?= 100
TEST_SEED_START ?= 9700000
TEST_WORKERS ?= 20
TEST_OUTPUT ?= reports/test_models.json
TEST_MATRIX_MODELS ?=
TEST_MATRIX_SEEDS ?= 50
TEST_MATRIX_SEED_START ?= 9850000
TEST_MATRIX_WORKERS ?= 20
TEST_MATRIX_OUTPUT ?= reports/test_matrix
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
EV2_SEARCH_NAME ?= ev2_hierarchical_$(shell date +%Y%m%d_%H%M%S)
EV2_SEARCH_RUN ?= $(SERVER_DATA)/runs/$(EV2_SEARCH_NAME)
EV2_SEARCH_LOCAL_RUN ?= $(SERVER_RESULTS)/$(EV2_SEARCH_NAME)
EV2_SEARCH_MINUTES ?= 5
EV2_SEARCH_POPULATION ?= 32
EV2_SEARCH_WORKERS ?= 20
EV2_START_GENOME ?=
LAST_EV2_SEARCH_RUN := $(SERVER_RESULTS)/LATEST_EV2_SEARCH_RUN
EV2_RESULT ?= $(shell test -f "$(LAST_EV2_SEARCH_RUN)" && cat "$(LAST_EV2_SEARCH_RUN)")
RANK1_ABLATION_SEEDS ?= 20
RANK1_ABLATION_OUTPUT ?= reports/rank1_nishchal_ablation.json
RANK1_ABLATION_VARIANTS ?=
RANK2_ABLATION_SEEDS ?= 20
RANK2_ABLATION_OUTPUT ?= reports/rank2_radiant_ablation.json
RANK2_ABLATION_VARIANTS ?=
EV45_ABLATION_SEEDS ?= 20
EV45_ABLATION_SEED_START ?= 9810000
EV45_ABLATION_OUTPUT ?= reports/ev45_ablation.json
EV45_ABLATION_VARIANTS ?=
EV45_ABLATION_OPPONENTS ?= 0801_ev1 0801_ev2 0801_ev3 0801_v1 0801_ev4 0801_ev5
PAIRED_SEARCH_NAME ?= paired_coordinates_$(shell date +%Y%m%d_%H%M%S)
PAIRED_SEARCH_RUN ?= $(SERVER_DATA)/runs/$(PAIRED_SEARCH_NAME)
PAIRED_SEARCH_LOCAL_RUN ?= $(SERVER_RESULTS)/$(PAIRED_SEARCH_NAME)
PAIRED_SEARCH_OPPONENTS ?= public_v31 public_v35 public_v36 public_v37
PAIRED_SEARCH_WORKERS ?= 20
PAIRED_STAGE0_SEEDS ?= 4
PAIRED_STAGE1_SEEDS ?= 16
PAIRED_STAGE2_SEEDS ?= 24
PAIRED_FINAL_SEEDS ?= 100
PAIRED_STAGE1_COUNT ?= 20
PAIRED_TOP_FIELDS ?= 5
PAIRED_FINALISTS ?= 3
LAST_PAIRED_SEARCH_RUN := $(SERVER_RESULTS)/LATEST_PAIRED_SEARCH_RUN
SCHEDULE_SEARCH_NAME ?= schedule_$(shell date +%Y%m%d_%H%M%S)
SCHEDULE_SEARCH_RUN ?= $(SERVER_DATA)/runs/$(SCHEDULE_SEARCH_NAME)
SCHEDULE_SEARCH_LOCAL_RUN ?= $(SERVER_RESULTS)/$(SCHEDULE_SEARCH_NAME)
SCHEDULE_SEARCH_OPPONENTS ?= public_v31 public_v35 public_v36 public_v37
SCHEDULE_SEARCH_WORKERS ?= 20
SCHEDULE_SEARCH_POPULATION ?= 64
SCHEDULE_STAGE0_SEEDS ?= 4
SCHEDULE_STAGE1_SEEDS ?= 16
SCHEDULE_STAGE2_SEEDS ?= 24
SCHEDULE_FINAL_SEEDS ?= 100
SCHEDULE_STAGE1_COUNT ?= 20
SCHEDULE_ELITE_COUNT ?= 6
SCHEDULE_FINALISTS ?= 3
LAST_SCHEDULE_SEARCH_RUN := $(SERVER_RESULTS)/LATEST_SCHEDULE_SEARCH_RUN
SCHEDULE_RESULT ?= $(shell test -f "$(LAST_SCHEDULE_SEARCH_RUN)" && cat "$(LAST_SCHEDULE_SEARCH_RUN)")
TRAJECTORY_SEARCH_NAME ?= trajectory_$(shell date +%Y%m%d_%H%M%S)
TRAJECTORY_SEARCH_RUN ?= $(SERVER_DATA)/runs/$(TRAJECTORY_SEARCH_NAME)
TRAJECTORY_SEARCH_LOCAL_RUN ?= $(SERVER_RESULTS)/$(TRAJECTORY_SEARCH_NAME)
TRAJECTORY_SEARCH_OPPONENTS ?= public_v31 public_v35 public_v36 public_v37
TRAJECTORY_SEARCH_WORKERS ?= 20
TRAJECTORY_SEARCH_POPULATION ?= 72
TRAJECTORY_STAGE0_SEEDS ?= 4
TRAJECTORY_STAGE1_SEEDS ?= 16
TRAJECTORY_STAGE2_SEEDS ?= 32
TRAJECTORY_FINAL_SEEDS ?= 100
TRAJECTORY_STAGE1_COUNT ?= 24
TRAJECTORY_ELITE_COUNT ?= 8
TRAJECTORY_FINALISTS ?= 4
LAST_TRAJECTORY_SEARCH_RUN := $(SERVER_RESULTS)/LATEST_TRAJECTORY_SEARCH_RUN
TRAJECTORY_RESULT ?= $(shell test -f "$(LAST_TRAJECTORY_SEARCH_RUN)" && cat "$(LAST_TRAJECTORY_SEARCH_RUN)")
CURRENT_GENOME_NAME ?= current_genome_$(shell date +%Y%m%d_%H%M%S)
CURRENT_GENOME_RUN ?= $(SERVER_DATA)/runs/$(CURRENT_GENOME_NAME)
CURRENT_GENOME_LOCAL_RUN ?= $(SERVER_RESULTS)/$(CURRENT_GENOME_NAME)
CURRENT_GENOME_OPPONENTS ?= public_v45_competitive_20260916 public_v43_competitive_20260915 public_v41_competitive_20260914 public_v38_low_pressure_20260914 results5_20260913
CURRENT_GENOME_WORKERS ?= 20
CURRENT_GENOME_POPULATION ?= 48
CURRENT_GENOME_SCREEN_SEEDS ?= 8
CURRENT_GENOME_RACE_SEEDS ?= 24
CURRENT_GENOME_FINAL_SEEDS ?= 200
CURRENT_GENOME_RACE_COUNT ?= 16
CURRENT_GENOME_ELITE_COUNT ?= 6
CURRENT_GENOME_FINALISTS ?= 4
CURRENT_GENOME_SEED ?= 20260917
CURRENT_GENOME_SEED_START ?= 21000000
LAST_CURRENT_GENOME_RUN := $(SERVER_RESULTS)/LATEST_CURRENT_GENOME_RUN
CURRENT_GENOME_RESULT ?= $(shell test -f "$(LAST_CURRENT_GENOME_RUN)" && cat "$(LAST_CURRENT_GENOME_RUN)")
MECHANISM_ABLATION_BASE ?= main.py
MECHANISM_ABLATION_OPPONENTS ?= public_v43_competitive_20260915 public_v38_low_pressure_20260914 public_v41_competitive_20260914 public_v41_survival_20260914
MECHANISM_ABLATION_SEEDS ?= 20
MECHANISM_ABLATION_WORKERS ?= 20
MECHANISM_ABLATION_OUTPUT ?= reports/mechanism_ablations.json

.PHONY: setup simulator-update simulator-check native-speedups-build server-native-speedups-build server-simulator-update server-simulator-check kaggle-check kaggle-download history-collect history-analyze cow-analyze cow-diagnose cow-search evaluate head-to-head submission-build test-import test-list test-models test-matrix server-sync-fast-runner server-test-models server-test-matrix server-mechanism-ablation server-rank1-ablation server-rank2-ablation server-ev45-ablation paired-search schedule-search schedule-status schedule-candidate schedule-use trajectory-search trajectory-status trajectory-candidate trajectory-use current-genome-search current-genome-status current-genome-candidate current-genome-use genome-train genome-status genome-candidate genome-use ev2-search ev2-candidate ev2-use server-check server-gpu-check server-update-code server-evaluate server-head-to-head server-hybrid-train server-structured-search server-structured-gate server-counterfactual-generate server-counterfactual-train server-counterfactual-evaluate server-push-replays server-push-datasets server-pull-results

setup:
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/python -m pip install -r requirements.txt

# Install the exact environment used by the current competition rules.
simulator-update:
	$(VENV)/bin/python -m pip install -r requirements.txt

# Verify rule constants, locked-tile behavior, and fast/standard parity.
simulator-check:
	PYTHONPATH=training $(VENV)/bin/python scripts/check_simulator.py

# Compile the parity-gated v4 simulator and agent hot paths. Repeated calls are
# cheap: the helper rebuilds only when sources, platform, or Python ABI change.
native-speedups-build:
	$(VENV)/bin/python scripts/ensure_native_speedups.py

server-simulator-update:
	ssh $(SERVER_HOST) 'set -eu; cd "$(SERVER_REPO)"; .venv/bin/python -m pip install "kaggle-environments==1.32.7"'

server-simulator-check: server-sync-fast-runner
	rsync -az scripts/check_simulator.py $(SERVER_HOST):$(SERVER_REPO)/scripts/
	ssh $(SERVER_HOST) 'set -eu; cd "$(SERVER_REPO)"; PYTHONPATH=training .venv/bin/python scripts/check_simulator.py'

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

submission-build:
	python3 -I -m py_compile main.py
	$(VENV)/bin/python scripts/validate_submission.py --agent main.py --output submission_fixed.tar.gz

# Store submission.tar.gz as test/<name>/main.py. Example: make test-import TEST_MODEL=rank1_20260801
test-import:
	test -n "$(TEST_MODEL)"
	$(VENV)/bin/python scripts/import_test_model.py "$(TEST_MODEL)" --archive submission.tar.gz --models-dir "$(TEST_DIR)"

test-list:
	@find "$(TEST_DIR)" -mindepth 2 -maxdepth 2 -name main.py -print 2>/dev/null | sed 's#^$(TEST_DIR)/##; s#/main.py$$##' | sort

# Evaluate main.py against all test models, or TEST_MODELS="name1 name2".
test-models:
	PYTHONPATH=training $(VENV)/bin/python scripts/evaluate_test_models.py --candidate "$(TEST_CANDIDATE)" --models-dir "$(TEST_DIR)" $(if $(strip $(TEST_MODELS)),--models $(TEST_MODELS),) --seed-start "$(TEST_SEED_START)" --seeds "$(TEST_SEEDS)" --workers "$(TEST_WORKERS)" --output "$(TEST_OUTPUT)"

# Round-robin all test models. Outputs JSON, Markdown, and CSV matrices.
test-matrix:
	PYTHONPATH=training $(VENV)/bin/python scripts/evaluate_test_matrix.py --models-dir "$(TEST_DIR)" $(if $(strip $(TEST_MATRIX_MODELS)),--models $(TEST_MATRIX_MODELS),) --seeds "$(TEST_MATRIX_SEEDS)" --seed-start "$(TEST_MATRIX_SEED_START)" --workers "$(TEST_MATRIX_WORKERS)" --output-dir "$(TEST_MATRIX_OUTPUT)"

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

server-sync-fast-runner:
	ssh $(SERVER_HOST) 'mkdir -p "$(SERVER_REPO)/training"'
	rsync -az training/fast_kaggriculture.py training/experimental_fast_kaggriculture.py training/experimental_fast_kaggriculture_v2.py training/experimental_fast_kaggriculture_v3.py training/production_fast_kaggriculture.py training/agent_runtime.py training/agent_runtime_native_extra.py training/reference_runtime.py training/native_*.cpp training/native_*.hpp $(SERVER_HOST):$(SERVER_REPO)/training/
	rsync -az scripts/prepare_native_simulator_source.py scripts/build_native_speedups.py scripts/build_native_speedups_turbo.py scripts/build_native_speedups_policy.py scripts/ensure_native_speedups.py $(SERVER_HOST):$(SERVER_REPO)/scripts/
	ssh $(SERVER_HOST) 'set -eu; cd "$(SERVER_REPO)"; .venv/bin/python -c "import pybind11" 2>/dev/null || .venv/bin/python -m pip install "pybind11>=3.0,<4"; .venv/bin/python scripts/ensure_native_speedups.py'

server-native-speedups-build: server-sync-fast-runner
	@printf 'Server v4 native extensions are current.\n'

server-test-models: server-sync-fast-runner
	test -d "$(TEST_DIR)"
	ssh $(SERVER_HOST) 'mkdir -p "$(SERVER_REPO)/scripts" "$(SERVER_REPO)/training"'
	rsync -az main.py $(SERVER_HOST):$(SERVER_REPO)/main.py
	rsync -az "$(TEST_CANDIDATE)" $(SERVER_HOST):$(SERVER_REPO)/candidate_under_test.py
	rsync -az scripts/evaluate_test_models.py $(SERVER_HOST):$(SERVER_REPO)/scripts/
	rsync -az --delete "$(TEST_DIR)/" $(SERVER_HOST):$(SERVER_REPO)/test/
	ssh $(SERVER_HOST) 'set -eu; cd "$(SERVER_REPO)"; mkdir -p "$(SERVER_DATA)/runs/manual"; PYTHONPATH=training .venv/bin/python scripts/evaluate_test_models.py --candidate candidate_under_test.py --models-dir test $(if $(strip $(TEST_MODELS)),--models $(TEST_MODELS),) --seed-start "$(TEST_SEED_START)" --seeds "$(TEST_SEEDS)" --workers "$(TEST_WORKERS)" --output "$(SERVER_DATA)/runs/manual/test_models.json"'
	mkdir -p "$(dir $(TEST_OUTPUT))"
	rsync -az $(SERVER_HOST):$(SERVER_DATA)/runs/manual/test_models.json "$(TEST_OUTPUT)"

server-test-matrix: server-sync-fast-runner
	test -d "$(TEST_DIR)"
	ssh $(SERVER_HOST) 'mkdir -p "$(SERVER_REPO)/scripts" "$(SERVER_REPO)/training" "$(SERVER_DATA)/runs/manual/test_matrix"'
	rsync -az scripts/evaluate_test_matrix.py $(SERVER_HOST):$(SERVER_REPO)/scripts/
	rsync -az --delete "$(TEST_DIR)/" $(SERVER_HOST):$(SERVER_REPO)/test/
	ssh $(SERVER_HOST) 'set -eu; cd "$(SERVER_REPO)"; mkdir -p "$(SERVER_DATA)/runs/manual/test_matrix"; OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=training .venv/bin/python scripts/evaluate_test_matrix.py --models-dir test $(if $(strip $(TEST_MATRIX_MODELS)),--models $(TEST_MATRIX_MODELS),) --seeds "$(TEST_MATRIX_SEEDS)" --seed-start "$(TEST_MATRIX_SEED_START)" --workers "$(TEST_MATRIX_WORKERS)" --output-dir "$(SERVER_DATA)/runs/manual/test_matrix"'
	mkdir -p "$(TEST_MATRIX_OUTPUT)"
	rsync -az $(SERVER_HOST):$(SERVER_DATA)/runs/manual/test_matrix/ "$(TEST_MATRIX_OUTPUT)/"

server-mechanism-ablation: server-sync-fast-runner
	ssh $(SERVER_HOST) 'mkdir -p "$(SERVER_REPO)/training" "$(SERVER_DATA)/runs/manual"'
	rsync -az "$(MECHANISM_ABLATION_BASE)" $(SERVER_HOST):$(SERVER_REPO)/mechanism_base.py
	rsync -az training/evaluate_mechanism_ablations.py $(SERVER_HOST):$(SERVER_REPO)/training/
	rsync -az --delete "$(TEST_DIR)/" $(SERVER_HOST):$(SERVER_REPO)/test/
	ssh $(SERVER_HOST) 'set -eu; cd "$(SERVER_REPO)"; OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=training .venv/bin/python training/evaluate_mechanism_ablations.py --base mechanism_base.py --models-dir test --opponents $(MECHANISM_ABLATION_OPPONENTS) --seeds "$(MECHANISM_ABLATION_SEEDS)" --workers "$(MECHANISM_ABLATION_WORKERS)" --output "$(SERVER_DATA)/runs/manual/mechanism_ablations.json"'
	mkdir -p "$(dir $(MECHANISM_ABLATION_OUTPUT))"
	rsync -az $(SERVER_HOST):$(SERVER_DATA)/runs/manual/mechanism_ablations.json "$(MECHANISM_ABLATION_OUTPUT)"

server-rank1-ablation: server-sync-fast-runner
	ssh $(SERVER_HOST) 'mkdir -p "$(SERVER_REPO)/training" "$(SERVER_DATA)/runs/manual"'
	rsync -az main.py $(SERVER_HOST):$(SERVER_REPO)/main.py
	rsync -az training/ev2_genome.py training/search_ev2_hierarchical.py training/evaluate_rank1_inspired_variants.py $(SERVER_HOST):$(SERVER_REPO)/training/
	rsync -az --delete "$(TEST_DIR)/" $(SERVER_HOST):$(SERVER_REPO)/test/
	ssh $(SERVER_HOST) 'set -eu; cd "$(SERVER_REPO)"; OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=training .venv/bin/python training/evaluate_rank1_inspired_variants.py --seeds "$(RANK1_ABLATION_SEEDS)" --workers "$(STRUCTURED_WORKERS)" $(if $(strip $(RANK1_ABLATION_VARIANTS)),--variants $(RANK1_ABLATION_VARIANTS),) --output "$(SERVER_DATA)/runs/manual/rank1_nishchal_ablation.json"'
	mkdir -p "$(dir $(RANK1_ABLATION_OUTPUT))"
	rsync -az $(SERVER_HOST):$(SERVER_DATA)/runs/manual/rank1_nishchal_ablation.json "$(RANK1_ABLATION_OUTPUT)"

server-rank2-ablation: server-sync-fast-runner
	ssh $(SERVER_HOST) 'mkdir -p "$(SERVER_REPO)/training" "$(SERVER_DATA)/runs/manual"'
	rsync -az main.py $(SERVER_HOST):$(SERVER_REPO)/main.py
	rsync -az training/ev2_genome.py training/search_ev2_hierarchical.py training/evaluate_rank2_inspired_variants.py $(SERVER_HOST):$(SERVER_REPO)/training/
	rsync -az --delete "$(TEST_DIR)/" $(SERVER_HOST):$(SERVER_REPO)/test/
	ssh $(SERVER_HOST) 'set -eu; cd "$(SERVER_REPO)"; OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=training .venv/bin/python training/evaluate_rank2_inspired_variants.py --seeds "$(RANK2_ABLATION_SEEDS)" --workers "$(STRUCTURED_WORKERS)" $(if $(strip $(RANK2_ABLATION_VARIANTS)),--variants $(RANK2_ABLATION_VARIANTS),) --output "$(SERVER_DATA)/runs/manual/rank2_radiant_ablation.json"'
	mkdir -p "$(dir $(RANK2_ABLATION_OUTPUT))"
	rsync -az $(SERVER_HOST):$(SERVER_DATA)/runs/manual/rank2_radiant_ablation.json "$(RANK2_ABLATION_OUTPUT)"

server-ev45-ablation: server-sync-fast-runner
	ssh $(SERVER_HOST) 'mkdir -p "$(SERVER_REPO)/training" "$(SERVER_DATA)/runs/manual"'
	rsync -az main.py $(SERVER_HOST):$(SERVER_REPO)/main.py
	rsync -az training/ev2_genome.py training/search_ev2_hierarchical.py training/evaluate_ev45_variants.py $(SERVER_HOST):$(SERVER_REPO)/training/
	rsync -az --delete "$(TEST_DIR)/" $(SERVER_HOST):$(SERVER_REPO)/test/
	ssh $(SERVER_HOST) 'set -eu; cd "$(SERVER_REPO)"; OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=training .venv/bin/python training/evaluate_ev45_variants.py --opponents $(EV45_ABLATION_OPPONENTS) --seeds "$(EV45_ABLATION_SEEDS)" --seed-start "$(EV45_ABLATION_SEED_START)" --workers "$(STRUCTURED_WORKERS)" $(if $(strip $(EV45_ABLATION_VARIANTS)),--variants $(EV45_ABLATION_VARIANTS),) --output "$(SERVER_DATA)/runs/manual/ev45_ablation.json"'
	mkdir -p "$(dir $(EV45_ABLATION_OUTPUT))"
	rsync -az $(SERVER_HOST):$(SERVER_DATA)/runs/manual/ev45_ablation.json "$(EV45_ABLATION_OUTPUT)"

paired-search: server-sync-fast-runner
	ssh $(SERVER_HOST) 'mkdir -p "$(SERVER_REPO)/training" "$(PAIRED_SEARCH_RUN)/source"'
	rsync -az main.py $(SERVER_HOST):$(SERVER_REPO)/main.py
	rsync -az training/ev2_genome.py training/search_paired_coordinates.py $(SERVER_HOST):$(SERVER_REPO)/training/
	rsync -az --delete "$(TEST_DIR)/" $(SERVER_HOST):$(SERVER_REPO)/test/
	ssh $(SERVER_HOST) 'set -eu; cd "$(SERVER_REPO)"; cp main.py training/ev2_genome.py training/search_paired_coordinates.py "$(PAIRED_SEARCH_RUN)/source/"; cp -R test "$(PAIRED_SEARCH_RUN)/source/"; OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=training .venv/bin/python training/search_paired_coordinates.py --incumbent main.py --engine test/0801_ev4/main.py --opponents $(PAIRED_SEARCH_OPPONENTS) --workers "$(PAIRED_SEARCH_WORKERS)" --stage0-seeds "$(PAIRED_STAGE0_SEEDS)" --stage1-seeds "$(PAIRED_STAGE1_SEEDS)" --stage2-seeds "$(PAIRED_STAGE2_SEEDS)" --final-seeds "$(PAIRED_FINAL_SEEDS)" --stage1-count "$(PAIRED_STAGE1_COUNT)" --top-fields "$(PAIRED_TOP_FIELDS)" --finalists "$(PAIRED_FINALISTS)" --output-dir "$(PAIRED_SEARCH_RUN)"'
	mkdir -p "$(PAIRED_SEARCH_LOCAL_RUN)"
	rsync -az $(SERVER_HOST):$(PAIRED_SEARCH_RUN)/ "$(PAIRED_SEARCH_LOCAL_RUN)/"
	mkdir -p "$(SERVER_RESULTS)"
	printf '%s\n' "$(PAIRED_SEARCH_LOCAL_RUN)" > "$(LAST_PAIRED_SEARCH_RUN)"
	@printf '\nDone. Results: %s\n' "$(PAIRED_SEARCH_LOCAL_RUN)"

schedule-search: server-sync-fast-runner
	ssh $(SERVER_HOST) 'mkdir -p "$(SERVER_REPO)/training" "$(SCHEDULE_SEARCH_RUN)/source"'
	rsync -az main.py $(SERVER_HOST):$(SERVER_REPO)/main.py
	rsync -az training/schedule_genome.py training/search_schedule.py training/promote_schedule.py $(SERVER_HOST):$(SERVER_REPO)/training/
	rsync -az --delete "$(TEST_DIR)/" $(SERVER_HOST):$(SERVER_REPO)/test/
	ssh $(SERVER_HOST) 'set -eu; cd "$(SERVER_REPO)"; cp main.py training/schedule_genome.py training/search_schedule.py training/promote_schedule.py "$(SCHEDULE_SEARCH_RUN)/source/"; cp -R test "$(SCHEDULE_SEARCH_RUN)/source/"; OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=training .venv/bin/python training/search_schedule.py --base main.py --models-dir test --opponents $(SCHEDULE_SEARCH_OPPONENTS) --workers "$(SCHEDULE_SEARCH_WORKERS)" --population "$(SCHEDULE_SEARCH_POPULATION)" --stage0-seeds "$(SCHEDULE_STAGE0_SEEDS)" --stage1-seeds "$(SCHEDULE_STAGE1_SEEDS)" --stage2-seeds "$(SCHEDULE_STAGE2_SEEDS)" --final-seeds "$(SCHEDULE_FINAL_SEEDS)" --stage1-count "$(SCHEDULE_STAGE1_COUNT)" --elite-count "$(SCHEDULE_ELITE_COUNT)" --finalists "$(SCHEDULE_FINALISTS)" --output-dir "$(SCHEDULE_SEARCH_RUN)"'
	mkdir -p "$(SCHEDULE_SEARCH_LOCAL_RUN)"
	rsync -az $(SERVER_HOST):$(SCHEDULE_SEARCH_RUN)/ "$(SCHEDULE_SEARCH_LOCAL_RUN)/"
	mkdir -p "$(SERVER_RESULTS)"
	printf '%s\n' "$(SCHEDULE_SEARCH_LOCAL_RUN)" > "$(LAST_SCHEDULE_SEARCH_RUN)"
	@printf '\nDone. Next: make schedule-status\n'

schedule-status:
	test -n "$(SCHEDULE_RESULT)"
	test -f "$(SCHEDULE_RESULT)/decision.json"
	$(VENV)/bin/python -c 'import json; d=json.load(open("$(SCHEDULE_RESULT)/decision.json")); s=d["selected"]; print("accepted=",d["accepted"]); print("reason=",d["reason"]); print("selected=",s["label"]); print("delta=",round(s["mean_delta"],1),"lower95=",round(s["lower_95_delta"],1),"worst=",round(s["worst_opponent_delta"],1))'

schedule-candidate:
	test -n "$(SCHEDULE_RESULT)"
	test -f "$(SCHEDULE_RESULT)/best_schedule.json"
	test -f "$(SCHEDULE_RESULT)/source/main.py"
	PYTHONPATH=training $(VENV)/bin/python training/promote_schedule.py --schedule "$(SCHEDULE_RESULT)/best_schedule.json" --base "$(SCHEDULE_RESULT)/source/main.py" --output candidate_main.py
	$(VENV)/bin/python -m py_compile candidate_main.py
	@printf 'Candidate ready: candidate_main.py\n'

schedule-use: schedule-candidate
	$(VENV)/bin/python -c 'import json; d=json.load(open("$(SCHEDULE_RESULT)/decision.json")); assert d["accepted"], "schedule acceptance gate was not met"'
	test -f "$(SCHEDULE_RESULT)/main_before_promotion.py" || cp main.py "$(SCHEDULE_RESULT)/main_before_promotion.py"
	cp candidate_main.py main.py
	$(MAKE) submission-build
	cp main.py "$(SCHEDULE_RESULT)/promoted_main.py"
	@printf '\nPromoted accepted schedule to main.py\n'

# Search explicit board geometry and five swappable action-order segments.
trajectory-search: server-sync-fast-runner
	ssh $(SERVER_HOST) 'mkdir -p "$(SERVER_REPO)/training" "$(TRAJECTORY_SEARCH_RUN)/source"'
	rsync -az main.py $(SERVER_HOST):$(SERVER_REPO)/main.py
	rsync -az training/trajectory_genome.py training/search_trajectory.py training/promote_trajectory.py $(SERVER_HOST):$(SERVER_REPO)/training/
	rsync -az --delete "$(TEST_DIR)/" $(SERVER_HOST):$(SERVER_REPO)/test/
	ssh $(SERVER_HOST) 'set -eu; cd "$(SERVER_REPO)"; cp main.py training/trajectory_genome.py training/search_trajectory.py training/promote_trajectory.py "$(TRAJECTORY_SEARCH_RUN)/source/"; cp -R test "$(TRAJECTORY_SEARCH_RUN)/source/"; OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=training .venv/bin/python training/search_trajectory.py --base main.py --models-dir test --opponents $(TRAJECTORY_SEARCH_OPPONENTS) --workers "$(TRAJECTORY_SEARCH_WORKERS)" --population "$(TRAJECTORY_SEARCH_POPULATION)" --stage0-seeds "$(TRAJECTORY_STAGE0_SEEDS)" --stage1-seeds "$(TRAJECTORY_STAGE1_SEEDS)" --stage2-seeds "$(TRAJECTORY_STAGE2_SEEDS)" --final-seeds "$(TRAJECTORY_FINAL_SEEDS)" --stage1-count "$(TRAJECTORY_STAGE1_COUNT)" --elite-count "$(TRAJECTORY_ELITE_COUNT)" --finalists "$(TRAJECTORY_FINALISTS)" --output-dir "$(TRAJECTORY_SEARCH_RUN)"'
	mkdir -p "$(TRAJECTORY_SEARCH_LOCAL_RUN)"
	rsync -az $(SERVER_HOST):$(TRAJECTORY_SEARCH_RUN)/ "$(TRAJECTORY_SEARCH_LOCAL_RUN)/"
	mkdir -p "$(SERVER_RESULTS)"
	printf '%s\n' "$(TRAJECTORY_SEARCH_LOCAL_RUN)" > "$(LAST_TRAJECTORY_SEARCH_RUN)"
	@printf '\nDone. Next: make trajectory-status\n'

trajectory-status:
	test -n "$(TRAJECTORY_RESULT)"
	test -f "$(TRAJECTORY_RESULT)/decision.json"
	$(VENV)/bin/python -c 'import json; d=json.load(open("$(TRAJECTORY_RESULT)/decision.json")); s=d["selected"]; print("accepted=",d["accepted"]); print("reason=",d["reason"]); print("selected=",s["label"]); print("delta=",round(s["mean_delta"],1),"lower95=",round(s["lower_95_delta"],1),"worst=",round(s["worst_opponent_delta"],1))'

trajectory-candidate:
	test -n "$(TRAJECTORY_RESULT)"
	test -f "$(TRAJECTORY_RESULT)/best_trajectory.json"
	test -f "$(TRAJECTORY_RESULT)/source/main.py"
	PYTHONPATH=training $(VENV)/bin/python training/promote_trajectory.py --trajectory "$(TRAJECTORY_RESULT)/best_trajectory.json" --base "$(TRAJECTORY_RESULT)/source/main.py" --output candidate_main.py
	$(VENV)/bin/python -m py_compile candidate_main.py
	@printf 'Candidate ready: candidate_main.py\n'

trajectory-use: trajectory-candidate
	$(VENV)/bin/python -c 'import json; d=json.load(open("$(TRAJECTORY_RESULT)/decision.json")); assert d["accepted"], "trajectory acceptance gate was not met"'
	test -f "$(TRAJECTORY_RESULT)/main_before_promotion.py" || cp main.py "$(TRAJECTORY_RESULT)/main_before_promotion.py"
	cp candidate_main.py main.py
	$(MAKE) submission-build
	cp main.py "$(TRAJECTORY_RESULT)/promoted_main.py"
	@printf '\nPromoted accepted trajectory to main.py\n'

# Search through the parity-gated production v4 runner. Includes coherent
# public-top3 opening trajectories, adaptive cow/sheep profiles, and terminal gates.
current-genome-search: server-sync-fast-runner
	ssh $(SERVER_HOST) 'mkdir -p "$(SERVER_REPO)/training" "$(CURRENT_GENOME_RUN)/source"'
	rsync -az main.py $(SERVER_HOST):$(SERVER_REPO)/main.py
	rsync -az training/current_genome.py training/search_current_genomes.py training/promote_current_genome.py $(SERVER_HOST):$(SERVER_REPO)/training/
	rsync -az --delete "$(TEST_DIR)/" $(SERVER_HOST):$(SERVER_REPO)/test/
	ssh $(SERVER_HOST) 'set -eu; cd "$(SERVER_REPO)"; cp main.py training/agent_runtime.py training/current_genome.py training/search_current_genomes.py training/promote_current_genome.py "$(CURRENT_GENOME_RUN)/source/"; cp -R test "$(CURRENT_GENOME_RUN)/source/"; OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=training .venv/bin/python training/search_current_genomes.py --base main.py --models-dir test --opponents $(CURRENT_GENOME_OPPONENTS) --workers "$(CURRENT_GENOME_WORKERS)" --population "$(CURRENT_GENOME_POPULATION)" --screen-seeds "$(CURRENT_GENOME_SCREEN_SEEDS)" --race-seeds "$(CURRENT_GENOME_RACE_SEEDS)" --final-seeds "$(CURRENT_GENOME_FINAL_SEEDS)" --race-count "$(CURRENT_GENOME_RACE_COUNT)" --elite-count "$(CURRENT_GENOME_ELITE_COUNT)" --finalists "$(CURRENT_GENOME_FINALISTS)" --seed "$(CURRENT_GENOME_SEED)" --seed-start "$(CURRENT_GENOME_SEED_START)" --output-dir "$(CURRENT_GENOME_RUN)"'
	mkdir -p "$(CURRENT_GENOME_LOCAL_RUN)"
	rsync -az $(SERVER_HOST):$(CURRENT_GENOME_RUN)/ "$(CURRENT_GENOME_LOCAL_RUN)/"
	printf '%s\n' "$(CURRENT_GENOME_LOCAL_RUN)" > "$(LAST_CURRENT_GENOME_RUN)"
	@printf '\nDone. Next: make current-genome-status\n'

current-genome-status:
	test -n "$(CURRENT_GENOME_RESULT)"
	test -f "$(CURRENT_GENOME_RESULT)/decision.json"
	$(VENV)/bin/python -c 'import json; d=json.load(open("$(CURRENT_GENOME_RESULT)/decision.json")); s=d["selected"]; print("accepted=",d["accepted"]); print("reason=",d["reason"]); print("selected=",s["label"]); print("reward_delta=",round(s["mean_delta"],1),"lower95=",round(s["lower_95_delta"],1),"worst_reward=",round(s["worst_opponent_delta"],1)); print("margin_delta=",round(s.get("mean_margin_delta",0),1),"worst_margin=",round(s.get("worst_opponent_margin_delta",0),1))'

current-genome-candidate:
	test -n "$(CURRENT_GENOME_RESULT)"
	test -f "$(CURRENT_GENOME_RESULT)/best_genome.json"
	test -f "$(CURRENT_GENOME_RESULT)/source/main.py"
	PYTHONPATH=training $(VENV)/bin/python training/promote_current_genome.py --genome "$(CURRENT_GENOME_RESULT)/best_genome.json" --base "$(CURRENT_GENOME_RESULT)/source/main.py" --output candidate_main.py
	$(VENV)/bin/python -m py_compile candidate_main.py
	@printf 'Candidate ready: candidate_main.py\n'

current-genome-use: current-genome-candidate
	$(VENV)/bin/python -c 'import json; d=json.load(open("$(CURRENT_GENOME_RESULT)/decision.json")); assert d["accepted"], "current-genome acceptance gate was not met"'
	test -f "$(CURRENT_GENOME_RESULT)/main_before_promotion.py" || cp main.py "$(CURRENT_GENOME_RESULT)/main_before_promotion.py"
	cp candidate_main.py main.py
	$(MAKE) submission-build
	cp main.py "$(CURRENT_GENOME_RESULT)/promoted_main.py"
	@printf '\nPromoted accepted current genome to main.py\n'

server-hybrid-train: server-sync-fast-runner
	ssh $(SERVER_HOST) 'set -eu; cd "$(SERVER_REPO)"; mkdir -p "$(HYBRID_RUN)"; OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=0 .venv/bin/python training/train_hybrid_ppo.py --output-dir "$(HYBRID_RUN)" --iterations "$(HYBRID_ITERATIONS)" --games-per-iteration "$(HYBRID_GAMES)" --workers "$(HYBRID_WORKERS)" --score800-reference "$(SERVER_REFERENCE)" --device cuda'

server-structured-search: server-sync-fast-runner
	ssh $(SERVER_HOST) 'set -eu; cd "$(SERVER_REPO)"; mkdir -p "$(STRUCTURED_RUN)"; OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=0 PYTHONPATH=training .venv/bin/python training/search_structured_strategies.py --minutes "$(STRUCTURED_MINUTES)" --population "$(STRUCTURED_POPULATION)" --proposal-multiplier 96 --stage1 12 --stage2 4 --workers "$(STRUCTURED_WORKERS)" --device cuda --output-dir "$(STRUCTURED_RUN)"'

# Five-minute search after the policy-family/search-space design pass.
ev2-search: server-sync-fast-runner
	ssh $(SERVER_HOST) 'mkdir -p "$(SERVER_REPO)/training" "$(SERVER_REPO)/test" "$(EV2_SEARCH_RUN)/source"'
	rsync -az training/ev2_genome.py training/search_ev2_hierarchical.py training/promote_ev2_genome.py $(SERVER_HOST):$(SERVER_REPO)/training/
	rsync -az --delete "$(TEST_DIR)/" $(SERVER_HOST):$(SERVER_REPO)/test/
	ssh $(SERVER_HOST) 'set -eu; cd "$(SERVER_REPO)"; cp training/ev2_genome.py training/search_ev2_hierarchical.py training/promote_ev2_genome.py "$(EV2_SEARCH_RUN)/source/"; cp -R test "$(EV2_SEARCH_RUN)/source/"; OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=training .venv/bin/python training/search_ev2_hierarchical.py --minutes "$(EV2_SEARCH_MINUTES)" --population "$(EV2_SEARCH_POPULATION)" --workers "$(EV2_SEARCH_WORKERS)" $(if $(strip $(EV2_START_GENOME)),--incumbent-genome "$(EV2_START_GENOME)",) --output-dir "$(EV2_SEARCH_RUN)"'
	mkdir -p "$(EV2_SEARCH_LOCAL_RUN)"
	rsync -az $(SERVER_HOST):$(EV2_SEARCH_RUN)/ "$(EV2_SEARCH_LOCAL_RUN)/"
	mkdir -p "$(SERVER_RESULTS)"
	printf '%s\n' "$(EV2_SEARCH_LOCAL_RUN)" > "$(LAST_EV2_SEARCH_RUN)"
	@printf '\nDone. Next: make ev2-candidate\n'

ev2-candidate:
	test -n "$(EV2_RESULT)"
	test -f "$(EV2_RESULT)/best_genome.json"
	$(VENV)/bin/python training/promote_ev2_genome.py --genome "$(EV2_RESULT)/best_genome.json" --base test/0801_ev2/main.py --output candidate_main.py
	python3 -I -m py_compile candidate_main.py
	PYTHONPATH=training $(VENV)/bin/python scripts/evaluate_test_models.py --candidate candidate_main.py --models-dir test --models 0801_ev1 0801_ev2 0801_ev3 0801_v1 --seeds 10 --workers 10 --output "$(EV2_RESULT)/candidate_screen.json"

ev2-use: ev2-candidate
	test -f "$(EV2_RESULT)/main_before_promotion.py" || cp main.py "$(EV2_RESULT)/main_before_promotion.py"
	cp candidate_main.py main.py
	$(MAKE) submission-build
	cp main.py "$(EV2_RESULT)/promoted_main.py"

server-structured-gate: server-sync-fast-runner
	ssh $(SERVER_HOST) 'set -eu; cd "$(SERVER_REPO)"; test -f "$(STRUCTURED_RUN)/best_genome.json"; found=0; for opponent in test/*/main.py; do test -f "$$opponent" || continue; found=1; name=$$(basename "$$(dirname "$$opponent")"); PYTHONPATH=training .venv/bin/python training/evaluate_strategy_genome.py --genome "$(STRUCTURED_RUN)/best_genome.json" --opponent "$$opponent" --seed-start 9700000 --seeds "$(STRUCTURED_GATE_SEEDS)" --workers "$(STRUCTURED_WORKERS)" --output "$(STRUCTURED_RUN)/gate_test_$${name}_fast.json"; done; test "$$found" = 1'

# One-command structured search: sync, train, validate, gate, and pull only this run.
genome-train: server-sync-fast-runner
	ssh $(SERVER_HOST) 'mkdir -p "$(SERVER_REPO)/training" "$(STRUCTURED_RUN)/source"'
	rsync -az main.py $(SERVER_HOST):$(SERVER_REPO)/main.py
	rsync -az training/strategy_genome.py training/search_structured_strategies.py training/evaluate_strategy_genome.py $(SERVER_HOST):$(SERVER_REPO)/training/
	test -d "$(TEST_DIR)"
	rsync -az --delete "$(TEST_DIR)/" $(SERVER_HOST):$(SERVER_REPO)/test/
	ssh $(SERVER_HOST) 'set -eu; cd "$(SERVER_REPO)"; cp main.py "$(STRUCTURED_RUN)/source/main.py"; cp training/fast_kaggriculture.py training/strategy_genome.py training/search_structured_strategies.py training/evaluate_strategy_genome.py "$(STRUCTURED_RUN)/source/"; cp -R test "$(STRUCTURED_RUN)/source/"; git rev-parse HEAD > "$(STRUCTURED_RUN)/source/git_commit.txt"; git diff > "$(STRUCTURED_RUN)/source/worktree.patch"'
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

server-counterfactual-generate: server-sync-fast-runner
	ssh $(SERVER_HOST) 'set -eu; cd "$(SERVER_REPO)"; mkdir -p "$$(dirname "$(CF_DATA)")"; OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/bin/python training/generate_branched_counterfactuals.py --agent main.py --opponent main.py --decision-days 8 12 16 20 24 --seed-start 1100000 --seeds "$(CF_SEEDS)" --workers 20 --profiles $(CF_PROFILES) --output "$(CF_DATA)"'

server-counterfactual-train:
	ssh $(SERVER_HOST) 'set -eu; cd "$(SERVER_REPO)"; mkdir -p "$(CF_RUN)"; CUDA_VISIBLE_DEVICES=0 .venv/bin/python training/train_counterfactual_value.py --input "$(CF_DATA)" --profiles $(CF_PROFILES) --output-dir "$(CF_RUN)" --epochs 400 --patience 80 --hidden-size 1024 --hidden-layers 6 --batch-size 1024 --device cuda --amp'

server-counterfactual-evaluate: server-sync-fast-runner
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

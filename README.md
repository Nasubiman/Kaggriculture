# Kaggriculture agent workspace

This workspace contains a reproducible public-history analysis pipeline and a
self-contained baseline agent for the Kaggriculture simulation competition.

## Setup

```bash
make setup
make kaggle-check
```

Python 3.11 or newer is required. Kaggle credentials stay outside the repository.

## Public Game History

Collect three recent public episodes for each of the current top five teams:

```bash
make history-collect
make history-analyze
```

Replay JSON files are stored under `replays/` and ignored by Git. The generated
strategy summary is written to `reports/public_history_summary.md`.

The current rank-1 adaptation study, including the reproducible day-10
milk/wool split and non-PPO improvement order, is in
[`reports/rank1_non_ppo_ideas_20260731.md`](reports/rank1_non_ppo_ideas_20260731.md).

## Current agent

`main.py` is the directly-submittable Cow Crown v1 agent. It:

- starts with two central sheep to create an early wool income stream;
- preserves and harvests the opening crop cycle before conversion;
- begins the cow transition on zero-indexed day 8;
- uses a server-trained day-8 decision tree to select 15 or 16 cows;
- expands northeast and keeps four sheep alongside the cows;
- hires eleven workers for daily feed, care, fertilizer, and harvest routing;
- maintains a wheat buffer through market purchases and two wheat plots;
- rehires workers on day 30 to harvest, return, drop, and sell final output.

The previous crop-only strategy is archived as
`agents/pulse_breaker_v2.py`, and the original baseline as
`agents/baseline_v1.py`.

Run the fixed-seed, both-seat evaluation:

```bash
make evaluate
make head-to-head
```

Submit after reviewing the generated evaluation:

```bash
.venv/bin/kaggle competitions submit kaggriculture \
  -f main.py \
  -m "Cow Crown v1: public-replay cow strategy"
```

See `reports/cow_strategy_implementation.md` for the replay evidence,
parameter search, and held-out results.

The latest counterfactual macro-policy improvement and its 200-game direct
incumbent evaluation are documented in
[`reports/macro_counterfactual_improvement_20260731.md`](reports/macro_counterfactual_improvement_20260731.md).

## Server migration

For moving development to a CPU/GPU server, including the files that are not
tracked by Git, environment recreation, parity checks, and the proposed
imitation-learning/self-play workflow, see
[`SERVER_MIGRATION_RUNBOOK.md`](SERVER_MIGRATION_RUNBOOK.md).

The configured hybrid workflow keeps replay collection and normal development
on the local Mac and uses `kag-server` only for compute-heavy work:

```bash
make server-check
make server-update-code
make server-evaluate
make server-head-to-head
make server-push-replays
make server-push-datasets
make server-pull-results
```

`make server-update-code` requires a clean local working tree and pushes the
current commit directly over SSH. The compute server does not need GitHub
credentials.

## Hybrid PPO prototype

The project includes an Orbit Wars-style hybrid reinforcement-learning
prototype. A neural policy makes one masked semantic decision per in-game day,
while `main.py` remains responsible for movement and other low-level legal
actions. Training uses PPO, a scripted/checkpoint opponent league, and PFSP-like
opponent sampling.

The compute server uses PyTorch 2.6.0 with CUDA 12.4:

```bash
make server-gpu-check
make server-hybrid-train
```

GPU dependencies are pinned in `requirements-gpu.txt`. Checkpoints and metrics
are written below the selected server run directory and are not committed.
Use `training/evaluate_hybrid_policy.py` for fixed-seed, both-seat Arena
evaluation. A learned checkpoint must beat the current `main.py` in held-out
Arena games before it is considered for submission.

See `reports/hybrid_ppo_gpu_prototype.md` for the architecture, first training
runs, and current limitations.

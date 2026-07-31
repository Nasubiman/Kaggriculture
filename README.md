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

`main.py` is the directly-submittable Rui Bridge v1 agent. It:

- reproduces the current rank-1 agent's exact day-0 public action sequence;
- opens with 16 melons, 6 carrots, 2 central cows, and 6 workers;
- harvests the melon capital cycle and converts on zero-indexed day 10;
- expands northeast and targets 8 cows plus 8 sheep;
- buys cows before sheep during the conversion;
- hires 11 workers for daily feed, care, fertilizer, and harvest routing;
- buys wheat as feed instead of dedicating mature-farm tiles to wheat;
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
  -m "Rui Bridge v1: rank-1 staged livestock strategy"
```

See
[`reports/rui_fixed_v1_implementation_20260731.md`](reports/rui_fixed_v1_implementation_20260731.md)
for the replay evidence, parameter search, and held-out results.

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

Training rollouts now use persistent workers and a parity-tested fast
interpreter path. On `kag-server`, the measured steady throughput is about
30.0 games/second, versus 2.0 before optimization. See
[`reports/server_training_speedup_20260731.md`](reports/server_training_speedup_20260731.md)
for benchmarks, fidelity checks, and the recommended 20-worker/60-game setup.

The first GPU counterfactual value-learning trial generated 4,600 profile
games and produced a held-out selector with a 60.25% direct win rate against
the current `main.py`. See
[`reports/counterfactual_gpu_value_trial_20260731.md`](reports/counterfactual_gpu_value_trial_20260731.md)
for the corrected profile semantics, standard-runner parity check, and the
remaining promotion gates.

The scaled multi-day, mixed-opponent GPU experiment uses about 66,000
counterfactual outcomes. Its day-8 policy reached 70% against `main.py` with
mean margin +613 while also improving KEEP margins against Pulse and score800.
See
[`reports/gpu_counterfactual_scaling_20260731.md`](reports/gpu_counterfactual_scaling_20260731.md).

The structured strategy search now covers 52 semantic fields, including mixed
opening, staged labor and land expansion, market-conditioned cow/sheep/goose
profiles, and a third crop/endgame transition. A five-minute server run found a
92.5%-win-rate held-out candidate and passed the strong-reference gate. See
[`reports/structured_strategy_gates_20260801.md`](reports/structured_strategy_gates_20260801.md).

For future promotion checks, Pulse and score800 are treated as obsolete weak
references. Structured candidates are compared directly with the current
`main.py`, then gated against the model extracted from `submission.tar.gz` via
`make server-structured-gate`.

The usual genome workflow is intentionally short:

```bash
make genome-train      # sync, train, validate, gate, and download
make genome-status     # show the latest scores
make genome-candidate  # create standalone candidate_main.py
make genome-use        # back up and replace main.py explicitly
```

Runs receive timestamped names automatically. Pass
`RUN=server-results/<run-name>` to the last three commands to select an older
run instead of the latest one. The complete Japanese procedure is in
`memo.txt`.

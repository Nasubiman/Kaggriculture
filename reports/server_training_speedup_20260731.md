# Server training throughput optimization

Date: 2026-07-31  
Host: `kag-server`

## Result

Steady-state hybrid PPO rollout throughput increased from about 2.0 to
33.1 games/second, a 16.5× improvement after the 2026-08-01 follow-up.

| Configuration | Games/update | Workers | Rollout seconds | Games/sec |
|---|---:|---:|---:|---:|
| old pool-per-update runner | 32 | 16 | ~15.9 | 2.01 |
| persistent pool | 32 | 16 | 12.9 | 2.48 |
| persistent pool, full CPU | 32 | 20 | 12.7 | 2.53 |
| persistent pool, aligned batch | 60 | 20 | 21.7 | 2.76 |
| fast interpreter runner | 60 | 20 | 4.1 | 14.60 |
| fast runner + target cache | 60 | 20 | 2.7–2.8 | 21.61–21.82 |
| reused environment + allocation-free routing | 60 | 20 | 2.4 | 24.56–24.64 |
| shared per-turn task candidates | 60 | 20 | 2.0 | 29.82–30.14 |
| default market-price cache | 60 | 20 | 1.8 | 32.29–34.17 |

With the final setup, a 60-game update takes approximately 2.0–2.1 seconds:

- rollout: approximately 1.8 seconds;
- GPU PPO update: 0.24–0.25 seconds;
- peak allocated GPU memory: about 19 MB.

The first update still pays worker import/startup cost and took 5.4 seconds.
Workers remain alive afterward, so longer runs operate at the steady rate.

### 2026-08-01 follow-up: default market-price cache

Profiling showed that the official interpreter recalculated the same
`(item, inventory)` default-market price tens of thousands of times per game.
The fast runner now uses a bounded 65,536-entry LRU cache for this pure
calculation. Custom market parameters still call the official function.

The optimization does not monkey-patch the public Kaggriculture module.
Instead, the fast runner reuses the official functions' code objects with an
isolated globals dictionary containing the cached price function. Standard
runner calls in the same process therefore remain untouched.

The production-shaped benchmark used five PPO updates, 60 games per update,
20 persistent workers, and the same seed/configuration for both versions.
The first update was excluded because it includes worker imports and startup.

| Version | Steady updates | Mean games/sec | Median games/sec | Mean rollout seconds |
|---|---:|---:|---:|---:|
| previous fast runner | 4 | 30.3678 | 30.2256 | 1.9767 |
| cached market prices | 4 | 33.0716 | 32.9131 | 1.8152 |

This is an 8.90% throughput increase (1.089×). A local single-process A/B
over 20 identical games measured a similar 9.47% increase. On the compute
server, 20 optimized fast-runner games exactly matched the standard runner's
summaries and complete game records.

The server artifacts are retained at:

- baseline: `/media/deepstation/storage/nakamura_y/kaggriculture/runs/fast_runner_benchmark_20260801/baseline_ab7245a`
- optimized: `/media/deepstation/storage/nakamura_y/kaggriculture/runs/fast_runner_benchmark_20260801/candidate_cache_v1`

`make server-sync-fast-runner` installs the current runner explicitly. All
server targets that use the fast path depend on this sync step, preventing a
local runner change from being omitted on the compute server.

## Changes

### Persistent rollout workers

`training/train_hybrid_ppo.py` now creates one multiprocessing pool for the
complete training run. Previously, every PPO update spawned 16 new Python
processes and each process imported PyTorch and all Kaggle environments.

The metrics log now records:

- `rollout_seconds`;
- `training_seconds`;
- `games_per_second`.

### Fast training runner

`training/fast_kaggriculture.py` invokes the official Kaggriculture
interpreter directly for trusted in-process training agents. It skips the
generic kaggle-environments work that dominated the profile:

- per-turn observation `deepcopy`;
- nested `structify` conversion;
- JSON Schema action/state validation;
- retaining all 720 replay states.

It does not reimplement game rules. Initialization, RNG, the Kaggriculture
interpreter, state transitions, and terminal rewards still come from the
installed official environment.

Each persistent worker now also reuses its already validated Environment
metadata. A deep copy of the small initial state starts each subsequent game,
and `env.info["seed"]` is replaced before play. This removes repeated
environment construction and JSON Schema validation without sharing mutable
episode state.

The full kaggle-environments runner remains in use for Arena evaluation and
promotion decisions. Fast mode is only the training rollout default and can
be disabled with `--no-fast-rollouts`.

### Cached deterministic targets

`main.py` previously recomputed and sorted the fixed cow, sheep, and wheat
target positions every in-game hour. These functions are now cached by:

- board size;
- cow target;
- sheep target;
- wheat-plot target.

Including all macro parameters in the key keeps the cache correct when PPO
changes a profile.

### Allocation-free field routing

The livestock router previously built a complete sortable candidate list for
every unit. It now tracks the lexicographically smallest task in one pass,
preserving the original tuple ordering while avoiding the temporary list.

Animal-care and field-work candidates are invariant across units within a
turn. They are now constructed once per turn and extended into each unit's
small dynamic list. The animal tile scan is also shared by action selection
and market planning. These changes increased the measured steady rate from
24.6 to 30.0 games/second.

### Server defaults

The server defaults now match the measured optimum:

```make
HYBRID_GAMES ?= 60
HYBRID_WORKERS ?= 20
```

Twenty workers were faster than 8, 10, 12, and 16 on the server's
10-core/20-thread Intel i9-9820X. Sixty games uses exactly three waves of
twenty workers.

The worker comparison was repeated after the final routing optimization:

| Workers | Aligned games | Steady games/sec |
|---:|---:|---:|
| 10 | 60 | 27.97–28.23 |
| 16 | 64 | 28.85–29.23 |
| 20 | 60 | 29.82–30.14 |

## Fidelity checks

The optimized path was compared with the standard runner using identical
seeds and agents.

1. A stochastic hybrid-policy game matched exactly on:
   final rewards, margin, status, all 30 semantic actions, action counts, and
   every shaped trajectory reward.
2. The cached and uncached scripted agents matched exactly over ten games,
   including final rewards and decision-state features.
3. Counterfactual generation matched exactly between fast and standard
   runners for all game records in the smoke comparison.
4. After environment reuse and all routing changes, eight sequential
   both-seat games matched the standard runner's complete saved game records
   exactly. This check exercises reuse across different seeds in one worker.

## Commands

Default accelerated training:

```bash
make server-hybrid-train \
  HYBRID_RUN=/media/deepstation/storage/nakamura_y/kaggriculture/runs/my_run \
  HYBRID_ITERATIONS=20
```

Explicit command:

```bash
cd /home/nakamura_y/agriculture/Kaggriculture
OMP_NUM_THREADS=1 \
OPENBLAS_NUM_THREADS=1 \
MKL_NUM_THREADS=1 \
CUDA_VISIBLE_DEVICES=0 \
.venv/bin/python training/train_hybrid_ppo.py \
  --output-dir /media/deepstation/storage/nakamura_y/kaggriculture/runs/my_run \
  --iterations 20 \
  --games-per-iteration 60 \
  --workers 20 \
  --device cuda
```

Use the standard runner for a diagnostic comparison:

```bash
.venv/bin/python training/train_hybrid_ppo.py \
  --output-dir /path/to/run \
  --iterations 2 \
  --games-per-iteration 60 \
  --workers 20 \
  --no-fast-rollouts \
  --device cuda
```

## Remaining bottleneck

The official interpreter and the scripted field router are now the main CPU
consumers. Further Python micro-optimization has a smaller ceiling because the
official interpreter alone accounts for roughly 30% of a profiled game.
More GPU memory does not speed up a single run because PPO optimization is
only about 11% of steady update time. The second GPU is best used for a
separate hyperparameter run; both jobs would need to split the 20 CPU threads
to avoid oversubscription.

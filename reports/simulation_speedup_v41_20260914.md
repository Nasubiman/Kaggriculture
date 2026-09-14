# V41 simulation throughput update (2026-09-14)

## Changes

1. Reuse loaded candidate/opponent modules inside each evaluation worker.
2. Replace generic `copy.deepcopy` with a memo-preserving fast path for exact
   dict/list/tuple/set agent data; unfamiliar objects use the stdlib fallback.
3. Dispatch current-genome search work as candidate/opponent seed batches,
   reducing repeated 340KB module compilation and multiprocessing IPC.
4. Keep `--no-reuse-agents`, `--no-optimize-agent-runtime`, and
   `--task-mode game` as reference/fallback modes.

## Measurements

Server: Intel i9-9820X, 10 physical cores / 20 logical CPUs. Workload: current
V41-derived `main.py` against `public_v41_competitive_20260914`, 100 seeds and
both seats (200 full 720-turn games).

| Mode | Workers | Seconds | Games/s |
|---|---:|---:|---:|
| fresh modules + stdlib deepcopy | 10 | 24.51 | 8.16 |
| reused modules + optimized deepcopy | 10 | 18.50 | 10.81 |
| reused modules + optimized deepcopy | 20 | 17.52 | 11.42 |

The selected 20-worker configuration is **1.40x** faster than the reference.
All 200 per-game records were identical between optimized and reference modes.

The official-vs-fast full-game parity check also passed with
`kaggle-environments==1.32.7`.

## Remaining bottleneck

Profiling one V41-vs-V41 game showed roughly half the runtime in each agent's
layered Python policy and the remainder in game transitions and copying. A much
larger next speedup requires compiling or rewriting the public policy's hot
planning layers, not GPU acceleration.

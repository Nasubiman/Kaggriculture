# Faster simulator v4 promotion (2026-09-15)

`origin/experimental/faster-simulator-v4` was merged into `main` after a
trajectory-parity gate. Production searches and evaluations now import
`training/production_fast_kaggriculture.py`; the previous
`training/fast_kaggriculture.py` remains the differential-test oracle and the
automatic fallback for unsupported configurations.

## Acceptance evidence

- Native simulator: 4 strong opponents × 5 seeds × both seats = 40 complete
  720-turn games. Every observation fingerprint, action fingerprint, terminal
  state, and reward matched the stable fast runner.
- Native candidate runtime: fast-runner parity for 8 games and official-runner
  parity for 4 games, both seats included.
- Native reference runtime: fast-runner parity for 14 games and official-runner
  parity for 10 games, including the v38 and both v41 snapshots.
- Production command: 4 opponents × 20 seeds × both seats = 160 games. The
  complete sorted `games` arrays and summaries from the stable and production
  commands were exactly equal.
- Local macOS build: all 9 pybind11 extensions built and imported successfully;
  the second build check skipped immediately from its source/ABI fingerprint.

The final server production comparison used the server's same candidate file
on both sides:

| runner | 160 games | wall time | throughput |
|---|---:|---:|---:|
| stable fast runner | 160 | 15.87 s | 10.08 games/s |
| production v4 | 160 | 12.07 s | 13.26 games/s |

That is a 1.31× end-to-end speedup for the normal 20-worker evaluation. The
isolated server measurements were 1.023× for the simulator, 1.140× for the
candidate runtime, and 1.103× for validated reference opponents. Gains vary by
model and worker count.

## Integration fixes made during promotion

The experimental branch contained a model-aware safe policy for fixed public
opponents, but `evaluate_test_models.py` did not use it. Applying the generic
candidate wrappers to an opponent can change its trajectory. Production
evaluation, matrix evaluation, and current-genome search now route named
opponents through `reference_runtime.optimize_reference_agent_module`; unknown
models stay on Python semantics until explicitly parity-tested.

The build no longer edits `agent_runtime.py` as a side effect. The extra native
layer is a normal source import, the official August-2026 market constants are
committed in the native simulator, the normalization helper is idempotent, and
the compiler flags now support both Linux and macOS.

## Commands

```bash
make native-speedups-build         # local; builds only when inputs/ABI changed
make server-native-speedups-build  # sync and build/skip on kag-server
make test-models                   # production v4 is the default
make server-test-models            # production v4 + native extensions
make current-genome-search         # production v4 + native extensions
```

Evidence files:

- `reports/v4_server_simulator_parity.json`
- `reports/v4_server_native_agent_runtime.json`
- `reports/v4_server_native_opponent_runtime.json`
- `reports/v4_server_stable_160.json`
- `reports/v4_server_production_160.json`
- `reports/v4_local_simulator_parity.json`

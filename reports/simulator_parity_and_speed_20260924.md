# Fast/official parity and the next speed ceiling (2026-09-24)

## Parity policy

No mismatch between the **promoted production fast runner** and the official
runner has been recorded for the same raw agent callables, rules, seed, and
configuration. The v4 promotion checked 40 full trajectories against the
stable fast runner and 160 production game records; earlier official-runner
checks also matched. On 2026-09-24, results29 matched the official runner
game-for-game on three seeds in both seats before a main change, and five more
seeds in both seats afterward.

There *have* been different outcomes when agent-loading/runtime optimization
settings differed. During v4 integration, applying generic native candidate
wrappers to public opponents changed their trajectories; model-specific
reference wrappers were introduced. In the current evaluation scripts,
`--optimize-agent-runtime` is therefore opt-in and the default is raw Kaggle
callables. This is not evidence that the production simulator itself diverged.

For routine strategy/threshold searches with unchanged game rules, dependency
versions, loader, and runner, use the fast runner without a redundant official
comparison for every candidate. Repeat official **trajectory** parity when the
simulator, rules/dependencies, loader, or runtime acceleration changes. Keep a
submission validation episode for packaging and Kaggle entry-point checks.

## Measured ceiling from optimizing the simulator alone

The server's actual `main.py` and opponent files matched the local SHA-256
hashes. `scripts/profile_episode_cost.py` used the same raw Kaggle callable
selection as production evaluation, reused loaded agents, and excluded one
warm-up game. `runner_and_wrapper_seconds` includes all rule transitions,
initialization, and timing-wrapper overhead, so it is an *upper bound* on pure
simulator time.

| Opponent | Games | Total | Main agent | Opponent agent | Runner + wrappers | Runner fraction |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| results29 | 12 | 20.881 s | 9.710 s | 10.660 s | 0.510 s | 2.44% |
| results18 | 8 | 13.362 s | 6.438 s | 6.577 s | 0.347 s | 2.60% |

Even an infinitely fast simulator could improve complete episode throughput
by at most 1.025–1.027× for these workloads. A 1.5× faster simulator alone
would improve complete episode throughput by only about 1.008–1.009×. Thus a
further 1.5× **end-to-end** speedup cannot come from simulator changes alone.
It would require substantial, parity-safe acceleration of both agent policies.
The cProfile run points to their layered Python decision logic and copying;
it does not identify an already validated 1.5× replacement.

Evidence: `episode_cost_results29_20260924.json`,
`episode_cost_results18_20260924.json`, and
`faster_simulator_v4_promotion_20260915.md`.

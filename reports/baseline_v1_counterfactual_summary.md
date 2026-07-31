# baseline_v1 counterfactual action search

## Method

Each mutation is applied to `agents/baseline_v1.py` during a rollout. After the
changed action, the environment is re-simulated from the same seed and the agent
receives the newly resulting observations. This avoids the invalid assumption
that later recorded actions remain valid after an earlier intervention.

The opponent is the user-provided Harvest Pulse agent. Player positions are
swapped for every seed.

## Policy-level mutations

Results over seeds 101, 202, and 303 (six games each):

| Mutation | Mean reward | Change | Mean margin |
|---|---:|---:|---:|
| None | 11,168.8 | — | -26,631.7 |
| Cap daily hires at 9 | 15,108.3 | +35.3% | -26,534.7 |
| Reverse every market-order list | 12,136.5 | +8.7% | -26,687.0 |

The nine-worker cap improves both own reward and mean margin, although it still
does not beat Harvest Pulse. Reversing all market orders improves absolute
reward but slightly worsens relative margin because the opponent also benefits
through the shared market.

## Single-step mutations

Nine individual multi-operation market turns were tested on seed 101 by
reversing only that turn's order. None improved final reward:

- six had no effect;
- one reduced reward slightly;
- two early-game reversals reduced mean reward from 11,358.5 to 10,774.5 and
  8,671.5 respectively.

This demonstrates that useful changes are non-local. A hill climber should
mutate policy parameters or repeated rules—not freely transpose arbitrary
recorded actions—and should optimize paired win margin across seeds rather than
single-game absolute reward.

# Pulse Breaker v2

## Objective

Beat the user-provided score-800 Harvest Pulse agent in more than 50% of direct
games while testing both player positions.

## Strategy change

Pulse Breaker retains Harvest Pulse's deterministic crop layout, seven-worker
cap, day-11 northeast expansion, and core-first task routing. Its main
counter-strategy is immediate melon-batch liquidation.

Harvest Pulse sells at most two melons per turn. Pulse Breaker sells its full
available batch, capturing the high-price portion of the shared market and
reducing the price received by the opponent's later clipped sales.

## Results

| Evaluation | Seeds | Games | Wins | Win rate | Mean reward | Opponent | Mean margin |
|---|---:|---:|---:|---:|---:|---:|---:|
| Parameter-development set | 701–704 | 8 | 8 | 100% | 30,626 | 25,805 | +4,821 |
| Held-out final set | 9001–9010 | 20 | 20 | 100% | 30,369 | 25,480 | +4,889 |
| Archived baseline_v1 holdout | 9101–9110 | 20 | 20 | 100% | 37,078 | 10,909 | +26,169 |
| starter/random regression | 101, 202, 303 | 12 | 12 | 100% | 46,482 | 1,746 | +44,736 |

All 40 reported games completed with status `DONE`. The held-out result exceeds
the requested 50% threshold by 50 percentage points.

Raw results:

- `reports/pulse_breaker_training.json`
- `reports/pulse_breaker_holdout.json`
- `reports/pulse_breaker_regression.json`
- `reports/current_vs_baseline_v1_holdout.json`

The previous submitted baseline is archived as `agents/baseline_v1.py`.

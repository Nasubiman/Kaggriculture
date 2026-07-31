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
| Held-out final set | 9001–9010 | 20 | 20 | 100% | 30,481 | 25,480 | +5,001 |
| Archived baseline_v1 holdout | 9101–9110 | 20 | 20 | 100% | 37,141 | 10,909 | +26,232 |
| starter/random regression | 101, 202, 303 | 12 | 12 | 100% | 46,482 | 1,746 | +44,736 |

All 40 reported games completed with status `DONE`. The held-out result exceeds
the requested 50% threshold by 50 percentage points.

Raw results:

- `reports/pulse_breaker_training.json`
- `reports/pulse_breaker_holdout.json`
- `reports/pulse_breaker_regression.json`
- `reports/current_vs_baseline_v1_holdout.json`

The previous submitted baseline is archived as `agents/baseline_v1.py`.

## Day-30 liquidation

The original Pulse Breaker passed all field actions on zero-indexed day 29 and
only sold items already in the shed. The revised agent now:

1. assigns harvestable plants or animals to available units;
2. stops accepting tasks that cannot be harvested and returned before season end;
3. routes carried inventory to the nearest shed-access tile;
4. issues `DROP` and matching `SELL` orders in the same turn.

On seed 9101 this recovered one otherwise-abandoned strawberry and changed the
reward from 36,641 to 36,956 (+315). Across the Harvest Pulse holdout, mean
reward increased by 112.2 without losing any games.

# Wool market timing search

Date: 2026-09-16

## Purpose

Improve the v43-derived incumbent without changing its validated production and
movement trajectory. The search therefore targeted the market timing of existing
wool output.

## Search-space change

The current genome now represents:

- every wool-sale hour from 0 through 23;
- retained wool inventory;
- a minimum acceptable wool price;
- sale intervals and day offsets;
- a per-sale quantity cap;
- sale start and end days;
- the sheep-extension stop day.

`training/search_wool_market.py` performs a hierarchical paired search: all 24
hours first, 192 expanded candidates next, a 24-candidate race, and an independent
400-game final gate. Candidates are ranked by raw win rate, mean margin, then own
reward.

## Selected genome

The selected change sells all available wool at hour 5 every day and stops the
extra sheep-extension hiring at day 28. The previous incumbent sold at hour 1 and
stopped at day 29.

On the independent 400-game search gate:

| Model | Wins | Win rate | Mean margin | Mean reward |
|---|---:|---:|---:|---:|
| Selected hour-5 genome | 362/400 | 90.5% | +496.5 | 99,014.3 |
| Hour-1 incumbent | 341/400 | 85.2% | +308.7 | 98,830.2 |

The candidate gained +184.2 own reward and +187.9 margin per game on identical
seeds.

## Independent league gate

The candidate was then tested over 100 seeds and both seats against each opponent:

| Opponent | Wins | Games | Win rate | Mean margin |
|---|---:|---:|---:|---:|
| public v43 competitive | 182 | 200 | 91.0% | +492.8 |
| public v41 competitive | 194 | 200 | 97.0% | +2,239.9 |
| public v41 survival | 194 | 200 | 97.0% | +2,241.9 |
| public v38 low pressure | 194 | 200 | 97.0% | +2,615.8 |
| results5 | 200 | 200 | 100.0% | +29,370.2 |
| pre-v43 incumbent | 194 | 200 | 97.0% | +2,299.7 |

There were no execution errors. Relative to the previous hour-1 gate on the same
evaluation seeds, mean margin improved against every opponent.

The selected standalone model and genome are stored in
`candidates/wool_hour5_20260916/` and promoted to `main.py`.

# Secondary market search

Date: 2026-09-16

## Motivation

Seven of the eight non-winning seeds in the hour-5 wool model were exact ties.
In most of those games, the model and public v43 produced identical actions because
no additional wool remained when the overlay ran. A second product-market overlay
was added to create an advantage without changing production or movement.

## Search

The first stage evaluated five products at every hour:

- WHEAT
- STRAWBERRY
- EGG
- MILK
- FERTILIZER

The second stage explored sale start/end days, retained inventory, minimum price,
and quantity caps. It used a 192-candidate screen, an 80-game race, and an
independent 400-game final gate. Candidates had to improve win rate without
regressing either mean margin or own reward.

## Selected genome

The selected overlay sells available STRAWBERRY at hour 22 on days 8 through 29,
while retaining two units. The previously selected wool policy remains unchanged:
sell all available wool at hour 5 and stop the extra sheep extension on day 28.

On the independent final gate:

| Model | Wins | Games | Win rate | Mean margin | Mean reward |
|---|---:|---:|---:|---:|---:|
| Wool + strawberry overlay | 391 | 400 | 97.8% | +966.8 | 99,652.4 |
| Wool-only incumbent | 348 | 400 | 87.0% | +457.0 | 99,456.0 |

The overlay improved own reward by +196.5 and margin by +509.8 on identical seeds.

## Independent league gate

| Opponent | Wins | Games | Win rate | Mean margin |
|---|---:|---:|---:|---:|
| public v43 competitive | 199 | 200 | 99.5% | +966.7 |
| public v41 competitive | 194 | 200 | 97.0% | +2,657.7 |
| public v41 survival | 194 | 200 | 97.0% | +2,659.7 |
| public v38 low pressure | 196 | 200 | 98.0% | +3,056.8 |
| results5 | 200 | 200 | 100.0% | +29,669.8 |
| pre-v43 incumbent | 192 | 200 | 96.0% | +2,720.4 |

There were no execution errors. Relative to the wool-only model on the same gate
seeds, mean margin increased against every opponent. The selected standalone model
and genome are stored in `candidates/secondary_strawberry_20260916/` and promoted
to `main.py`.

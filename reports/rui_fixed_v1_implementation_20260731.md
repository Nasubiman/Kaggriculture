# Rui Bridge v1 implementation and evaluation

## Outcome

The fixed strategy reconstructed from RuiKimura4 public replays has been
promoted to `main.py`.

| Gate | Games | Wins | Ties | Win rate | Mean reward | Mean margin |
|---|---:|---:|---:|---:|---:|---:|
| Versus previous `main.py`, selection | 200 | 140 | 0 | 70% | 71,016 | +7,083 |
| Fast/standard parity seeds | 40 | 30 | 0 | 75% | 70,505 | +7,513 |
| Pulse, standard runner | 20 | 20 | 0 | 100% | 101,943 | +68,678 |
| score800, standard runner | 20 | 20 | 0 | 100% | 104,892 | +73,611 |

The fast and standard runner result JSONs were exactly equal for all 40
parity games, including every per-game reward and margin.

## Promoted strategy

- Day 0 uses the exact 24-hour action sequence visible in the rank-1 replay.
- Opening layout: 16 melons, 6 carrots, 2 cows, 6 workers.
- Day 10 unlocks NE and converts the mature melon capital into livestock.
- Mature targets: 8 cows and 8 sheep.
- Cows are purchased before sheep during conversion.
- Mature worker target: 11.
- Wheat is purchased; no mature wheat tile is reserved.
- The earlier day-8 15/16-cow decision tree is disabled.

## Search observations

The initial generic reconstruction planted only 11 of 16 melons on Day 0 and
won 27% of 100 games. Replaying the exact public Day-0 choreography planted
all 16 melons and raised the candidate to 47% over 200 games. Buying cows
before sheep and using 11 rather than 12 mature workers produced the final
70% candidate.

Large strawberry reconstructions did not transfer to the current generic
router. The 20-strawberry version won 0/100 in the first screen and 11/200
after the scripted opening. Four strawberry tiles also remained below 50%.
The leader's strawberry schedule therefore needs a dedicated cyclic router;
it was not included in the promoted version.

Disabling carrot replanting, although closer to the public leader, reduced a
40-game screen from 28 wins to 27 and cut mean margin from +9,306 to +4,177.
The promoted version retains replanting because the rest of its routing is
not yet an exact clone of the leader.

## Artifacts

- Search driver: `training/search_rui_fixed.py`
- Rank-1 analysis: `reports/rank1_rui_behavior_20260731.md`
- Selection: `server-results/rui_fixed_v1/tune100.json`
- Fast parity: `server-results/rui_fixed_v1/parity_fast.json`
- Standard parity: `server-results/rui_fixed_v1/parity_standard.json`
- Pulse gate: `server-results/rui_fixed_v1/vs_pulse_standard.json`
- score800 gate: `server-results/rui_fixed_v1/vs_score800_standard.json`


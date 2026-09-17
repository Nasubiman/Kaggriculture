# Sale-race mechanism transfer, 2026-09-17

The user allowed switching the base model if it improved win rate. We first
tested `results12_20260917` as a whole-model base. It beat results11/13 in
80% of 100-seed, both-seat games, but won only 89% against public v45; the
then-current agent was around 99% against v45 and beat results12 directly.
The full base switch was therefore rejected.

The useful difference was its sale-race idea: when the existing route is
scheduled to sell an item in the next three turns and the item is already in
the shed, offer it earlier. We implemented that as a late wrapper around the
current agent. It also puts independent sales before purchases in the market
order. It does not change the route, production planner, or frozen genome.

## Independent paired evaluation

Fast production simulator, unoptimized agent code, 200 unseen seeds x both
seats = 400 games per opponent, seed start 47,000,000. The before/after runs
use identical seeds and rivals. The after run uses the integrated, standalone
`main.py`, not the experimental importing wrapper.

| Opponent | Before | After | Extra wins | Mean margin gain |
| --- | ---: | ---: | ---: | ---: |
| results11 | 247/400 (61.75%) | 337/400 (84.25%) | +90 | +417.5 |
| results12 | 281/400 (70.25%) | 370/400 (92.5%) | +89 | +374.6 |
| results13 | 245/400 (61.25%) | 337/400 (84.25%) | +92 | +418.1 |
| public v45 | 395/400 (98.75%) | 395/400 (98.75%) | 0 | +256.7 |
| results5 | 397/400 (99.25%) | 397/400 (99.25%) | 0 | -25.3 |

There were no simulation errors. Results5's mean own reward fell by 145.9
and mean margin by 25.3 despite unchanged wins, so this is not a claim of
uniform reward improvement. The preliminary 100-seed paired evaluation also
showed gains of +32, +28, +32 wins against results11/12/13, respectively,
with unchanged wins against v45/results5.

The standalone `main.py` matched the experimental wrapper game-for-game on
5 further seeds x both seats x 3 new rivals. The fast and standard runners
also matched game-for-game on those 30 games. In one full episode, the new
mechanism advanced 49 units on 18 turns and reported zero internal errors.
`make submission-build` passed Kaggle's raw-file loader and validation episode
for both seats, producing `submission_fixed.tar.gz`.

Raw files: `sale_advance_incumbent_holdout200_20260917.json`,
`sale_advance_integrated_holdout200_20260917.json`,
`sale_advance_integrated_fast5_20260917.json`, and
`sale_advance_integrated_standard5_20260917.json` in this directory.

# Cow Crown v1

## Public-replay evidence

Twelve recent public games from the top three leaderboard teams were collected
on 2026-07-31. The current rank-one team averaged 19.5 deployed cows across the
sample, first bought cows on day 8.8, and used 13.5 hands at peak. In one
105,665-point replay, its farm reached 22 cows on day 13 and maintained roughly
11–12 hands thereafter.

The useful pattern was broader than simply buying cows:

1. begin with a small livestock and crop economy;
2. use early wool and mature melon sales to finance the conversion;
3. place cows close to the central shed;
4. maintain enough hands and wheat to feed, care for, and collect from every
   animal;
5. hire again on the final day so animal output can be returned and sold.

The raw replay summary is in `reports/cow_strategy_analysis.md`.

## Selected strategy

Cow Crown starts two sheep in central pastures, then preserves the opening crop
cycle through its profitable harvest. On day 11 it buys northeast land and
converts central tiles into twenty cow pastures. It targets twelve hands per
day, buys wheat to keep an animal-sized buffer, and uses two remaining plots
for wheat.

Field priorities are:

1. harvest mature cash crops during the transition;
2. place carried animals and complete missing pastures;
3. feed animals and replenish carried wheat;
4. care, collect fertilizer, and harvest milk or wool;
5. maintain the two wheat plots.

On day 30, hands are rehired and only harvest tasks that can still be completed,
returned to the shed, and sold before the episode ends are accepted.

## Parameter selection

The main alternatives varied cow start day, cow target, sheep target, and hand
count. More livestock was not automatically better: 24–26 cows and fourteen
hands lost reward to extra feed, hiring, and travel. The robust region was
twenty to twenty-two cows and twelve hands.

The selected day-11 / 20-cow / 2-sheep configuration scored:

| Set | Seeds | Games | Wins | Mean reward | Mean margin |
|---|---:|---:|---:|---:|---:|
| Development | 101, 202 | 4 | 4 | 109,030 | +72,278 |
| Parameter holdout | 303, 404, 505 | 6 | 6 | 104,778 | +68,069 |

## Final held-out comparison

Neither final set was used for parameter selection, and both player seats were
tested for every seed.

| Opponent | Seeds | Games | Wins | Win rate | Mean reward | Opponent | Mean margin |
|---|---:|---:|---:|---:|---:|---:|---:|
| Archived Pulse Breaker v2 | 611–615 | 10 | 10 | 100% | 105,481 | 35,832 | +69,649 |
| User-provided score-800 agent | 7101–7105 | 10 | 10 | 100% | 107,046 | 34,585 | +72,462 |

All games completed with status `DONE`. Local episode rewards are useful for
relative testing but do not directly predict Kaggle leaderboard rating.

Raw results:

- `reports/cow_variant_search.json`
- `reports/cow_vs_pulse_breaker.json`
- `reports/cow_vs_score800.json`

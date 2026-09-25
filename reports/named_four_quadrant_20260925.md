# Four-quadrant public replay comparison (2026-09-25)

Source: fifteen completed public Kaggle replays each for Unknown Mother-Goose
(best public submission `56525914`) and Fourth Quadrant (`56521806`). Raw
replays and manifest are in `replays/public_20260925_4q_named/`; the extracted
per-game observations are in `reports/named_four_quadrant_20260925.json`.
The Kaggle leaderboard query on 2026-09-25 listed them fourth and seventh,
respectively. These are public game histories, not their source code.
Actions are stored one row after their triggering observation, so purchase
steps below account for that offset.

| Team | Third land purchase | Fourth land purchase | Occupied SE tiles at step 288 | Occupied SE tiles at step 360 | SE at step 432 |
| --- | ---: | ---: | ---: | ---: | --- |
| Fourth Quadrant | 197–203 (mean 198.3) | 247–249 (12/15 at 248) | mean 23.8/25 | mean 24.1/25 | mean 16.3 wheat, 3.0 strawberry; some cow/sheep |
| Unknown Mother-Goose | 219–221 (14/15 at 219) | 252–254 in 14/15; one at 276 | mean 16.4/25 | mean 24.0/25 | mean 8.9 wheat, 4.7 strawberry, diversified tomato/carrot |

Both teams purchased four quadrants in all thirty player-games. Their fourth-land timing
barely varied despite different early shops, unlike the current DECEM-derived
experimental gate that requires ICE_CREAM_SHOP + SMOOTHIE_SHOP, high prices,
and at least 10,000 cash. Fourth Quadrant often placed BUY_LAND after sales
inside the *same* market action, with only 1,208–5,990 cash in the preceding
observation. A cash-only gate misses those purchases.

The two teams are not using the same four-quadrant policy: Fourth Quadrant
opens land earlier and fills the southeast mostly with wheat by day 12;
Unknown Mother-Goose opens slightly later, fills it by roughly day 15, and
changes crop mix across games. A single strawberry replay tape is therefore
not a faithful model of either team. In particular, the current experimental
DECEM tape starts its southeast overlay at step 289, after both teams have
already populated much of that quadrant.

Next search space: treat (1) third/fourth land timing and same-turn financing,
(2) southeast field plan, and (3) worker/harvest routes as separate linked
decisions. Start with the Fourth Quadrant wheat-heavy and Mother-Goose mixed
crop archetypes. Infer their conditional decisions from many more public games,
then test each archetype against the unchanged main.py on paired random seeds
and a diverse opponent league. Do not hard-code the replay seeds or copy
an entire action tape into the submitted policy.

The separate 14-strawberry DECEM overlay gained just 5 wins in 8,000 screened
games on a fresh 1,000-seed test (results14/results20/results23/results29),
with +22 wins against the two stronger models and -17 against the two weaker
ones. That is not yet a robust reason to replace main.py.

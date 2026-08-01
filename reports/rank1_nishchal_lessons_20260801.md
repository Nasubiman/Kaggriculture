# Current rank-1 verification: nishchal jain (2026-08-01 JST)

## Latest public data

- Kaggle leaderboard checked on 2026-08-01: rank 1 `nishchal jain`, score 1427.4.
- Submission id: 55147073.
- Fifteen recent public episodes were collected at
  `2026-08-01T06:22:11Z`.
- Public sample: 10/15 wins, mean reward 113,600, mean margin +2,875.
- Public games are neither random nor directly comparable with the local fixed
  league, so observed choices were tested with paired seeds before acceptance.

## Observable policy

- Day 0--8: six hands; day 9: about eleven; day 11 onward: thirteen.
- Land purchases occur on day 8 and day 11.
- Opening field: about five pastures, four cows, nine melon and eleven wheat.
- Herd expands from four cows to five cows, then adds sheep, reaching a fixed
  mature profile of seven cows and six sheep.
- Average field actions include 105.7 FERTILIZE actions per game. Fertilizer is
  also sold (173.5 units/game), so the policy both applies profitable stock and
  liquidates the remainder.
- No carrots are maintained in the observed day-end profile.

## Twenty-seed structural screen

All variants faced ev1, ev2, ev3 and the previous v1 on common seeds and both
seats. Values are league mean rewards.

| Variant | Mean reward | Delta vs incumbent | Decision |
|---|---:|---:|---|
| Rank-1 herd totals/timing/layout | 123,376.1 | +3,912.6 | Validate |
| Rank-1 herd + opening crop | 120,666.2 | +1,202.7 | Inferior to herd-only |
| Incumbent | 119,463.5 | — | Baseline |
| 13 hands | 119,136.8 | -326.7 | Reject |
| Melon 9 / wheat 11 opening | 118,769.5 | -694.0 | Reject |
| 13 hands + day 8/11 land | 116,115.6 | -3,347.9 | Reject |
| Day 8/11 land | 115,955.4 | -3,508.1 | Reject |
| Full static imitation | 114,059.2 | -5,404.3 | Reject |

## One-hundred-seed validation

The herd-only candidate changes:

- herd totals: `4 -> 8 -> 12` to `5 -> 9 -> 13`;
- expansion start: day 7 to day 5;
- animal capacity by quadrant: `4 / 5 / 3` to `5 / 5 / 3`.

It retains the incumbent's land timing, crop policy, twelve-hand ceiling,
fertilizer policy and market-adaptive cow/sheep selection.

| Opponent | Incumbent | Herd candidate | Delta |
|---|---:|---:|---:|
| ev1 | 121,901.1 | 123,108.4 | +1,207.3 |
| ev2 | 117,362.9 | 119,800.1 | +2,437.1 |
| ev3 | 126,306.7 | 129,642.4 | +3,335.8 |
| previous v1 | 119,419.1 | 122,371.5 | +2,952.5 |
| **League mean** | **121,247.4** | **123,730.6** | **+2,483.2** |

- Games: 100 seeds x 4 opponents x both seats = 800 games per policy.
- Candidate win rate: 100%.
- Candidate errors: 0.
- Worst-opponent mean reward: 119,800.1.

## Conclusion

The rank-1 data produced one robust improvement: slightly earlier and larger
livestock expansion. Directly copying the leader's later land schedule, early
wheat field or thirteen-hand ceiling is harmful inside the current ev2 engine.
The leader's choices form a coordinated policy; isolated imitation is not
equivalent to copying the whole engine.

The herd candidate was promoted to `main.py` after the explicit adoption
decision. The previous fertilizer-v2 main is retained as
`server-results/rank1_nishchal_herd_100/main_before_promotion.py`.

Supporting artifacts:

- `replays/rank1-20260801-latest/manifest.json`
- `reports/rank1_nishchal_summary.md`
- `reports/rank1_nishchal_adaptation.md`
- `reports/rank1_nishchal_ablation.json`
- `reports/rank1_nishchal_herd_100.json`

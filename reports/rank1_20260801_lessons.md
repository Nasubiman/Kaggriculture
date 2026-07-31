# Current rank-1 lessons (2026-08-01 JST)

## Data

- Collected from the Kaggle public leaderboard at 2026-08-01 00:34 JST.
- Rank 1: `smlcr`, public score 1406.8.
- Sample: the latest 10 public games; 10 wins, mean reward 113,733,
  mean margin +16,950.
- These are observable public games, not a random or complete evaluation set.

## Observable strategy

1. Day 0 is mixed, not cow-only: 2 cows, 2 sheep, 6 hands, 4 pastures,
   11 melon, 2 carrot, 1 strawberry, and 1 wheat are prepared.
2. Labor ramps from 6 on day 0 to 7, 8, 9, and then 12 by day 9.
3. The first extra quadrant is bought on day 7 in all 10 games. The second is
   bought on day 10 or 11. The agent therefore operates three quadrants.
4. Livestock is market-adaptive. Observed mature profiles range from 10 cows / 2
   sheep to 4 cows / 8 sheep, with 0--4 geese in lower-milk-price games.
5. Cows and sheep occupy central service-efficient positions. The two positions
   used in all 10 games were cows at (3,4), (4,4) and sheep at (4,2), (4,3).
6. Crop policy has more than two phases. It expands strawberry production in
   the early/middle game, uses substantial wheat later, and changes again near
   day 26 before full day-29 liquidation.
7. Early cash is kept near zero and reinvested. Mean observed money rises from
   84 at the end of day 7 to 13,305 on day 12 and 104,170 on day 28.
8. Day 29 aggressively harvests/drops and sells all major products. The current
   agent already has a similar final-day mechanism, so this is not the first
   area to change.

## Gap in the current search space

The current genome can choose fixed cow/sheep targets and two transition days,
but it cannot adequately represent the rank-1 behavior:

- no goose target/profile;
- no market-conditioned choice among livestock profiles;
- only one extra land purchase in the current `main.py`;
- no gene for fixed day-7 and day-10/11 land expansion;
- no multi-stage crop schedule such as strawberry -> wheat -> endgame;
- no staged labor ramp to 12 hands;
- opening supports one animal kind, not the observed 2-cow/2-sheep mixture.

## Recommended next search-space expansion

Priority order:

1. Add `land_1_day`, `land_2_day`, and `land_count` genes.
2. Add a mixed 2-cow/2-sheep opening and staged hand targets.
3. Add three livestock profiles (cow-heavy, sheep-heavy, goose-mixed) selected
   from milk/wool/egg prices and market inventory around days 7 and 10.
4. Add at least two more crop gates: expansion crop, late wheat, and endgame
   maturity-aware crop/stop-planting policy.
5. Add central mixed-animal layouts to the layout families.

The public evidence supports market-aware adaptation. Because the shared market
is affected by the opponent, this is indirectly opponent-aware; it does not by
itself prove that rank 1 reacts to the opponent's physical movement.

## Implementation status

These gates were added to the 52-field genome on 2026-08-01. A five-minute
search selected the additional crop/endgame transition and reached 92.5% over
200 held-out games against the previous `main.py`. The other gates remain in
the search space but were not selected by that short run. See
`reports/structured_strategy_gates_20260801.md`.

# Current rank-1 lessons: Majkel1337 (2026-09-13 JST)

## Evidence

- Kaggle leaderboard rank 1 at collection time: `Majkel1337`, submission `56156662`.
- Twenty latest public games were collected; 19 wins, mean reward 111,657,
  mean margin +6,992.
- Public opponents and seeds differ from local evaluation, so the rank-1 score
  must not be compared directly with our local 96,697 mean reward.
- Submitted market orders can be unaffordable or invalid; conclusions about
  owned assets use observed farm states, not request counts.

## What the policy appears to do

### 1. Multi-turn opening, not a single opening-order trick

The first four market actions were identical in all 20 games:

1. Buy one cow and five wheat.
2. Sell one wheat, request four hires, buy one cow and three sheep.
3. Sell one wheat.
4. Sell one wheat and buy one wheat.

It then continues small one-unit wheat operations while purchasing the first
melon and wheat seeds.  The opening therefore couples real investment,
liquidity for hires, and price movement over several turns.  Our current model
instead overrides only turn zero with a large wheat round trip.  The cyclic
q25/q35/q90 counters seen locally are consistent with that narrower design.

### 2. Three economic phases

- Days 0--5: five pastures, two cows, three sheep, 12 melons, then a gradual
  strawberry build.  Actual hands progress roughly 4 -> 6.
- Days 6--12: expansion on day 6 and again around days 8--9; hands reach 11,
  the herd and pasture area specialize, wheat rises sharply, and all melons
  disappear by day 12.
- Days 14--29: small, gradual carrot introduction rather than our large late
  conversion.  Strawberry acreage declines from about 28 to almost zero,
  wheat remains the feed/input backbone, and terminal liquidation begins
  before the final day.

This is a phase schedule with transition gates, rather than a single static
field target.

### 3. Strong observable livestock adaptation

From day 8 onward, `cow count - sheep count` has correlation about +0.95 to
+0.97 with `milk price - wool price`.  When milk is expensive relative to wool,
the policy becomes cow-heavy; when wool is expensive, it becomes sheep-heavy;
near parity it uses a balanced herd.  This corrects the direction of the old
August heuristic that predicted the opposite relationship.

The mature day-18 profiles range from 5 cows / 12 sheep to 14 cows / 3 sheep.
Pasture counts range from 8 to 20 and geese range from 0 to 4.  Thus land,
pasture and goose allocation also appear conditional, not fixed constants.
The animal balance is correlated with the opponent's balance too, but market
prices are jointly affected by both players; public replay alone cannot prove
whether the direct input is the opponent layout or the price signal.

### 4. Deliberate within-day ordering

- Feed is concentrated around hours 3--9.
- Care is concentrated around hours 4--10.
- Harvest and fertilize concentrate around hours 11--17.
- Plant and water concentrate around hours 16--22.

Our policy has broadly similar phases, but its planting has a larger hour-23
spike and its harvesting is earlier.  The rank-1 order reduces competition
between animal maintenance, collection, crop work and shed delivery.

### 5. Leaner fixed labor and earlier terminal contraction

The leader stabilizes at 11 hands from day 10 through day 27.  Our six-game
trace averaged above 11 on several days and sometimes reached 12.  The leader
drops to 10 hands on days 28--29, sharply reduces care/feed, and lets sheep and
crops decline into liquidation.  Our policy still issues care/feed work on the
last day and retains a more static herd, so terminal labor and animal shutdown
are credible improvement targets.

## Differences from the current model

| Dimension | Current model | Rank-1 public behavior |
|---|---|---|
| Opening | One large turn-0 wheat round trip; seat-conditioned q30/q5 | Small multi-turn wheat operations coupled to cow/sheep/hire purchases |
| Day-0 herd | 2 cows, 2 sheep | 2 cows, 3 sheep |
| Day-0 crops | 12 melons, 7 wheat | 6 melons, about 9 wheat |
| Expansion | Large day-6 pasture jump; mostly fixed mature layout | Day 6/8/9 staged expansion; pasture and herd size vary strongly |
| Mature animals | Usually about 8 cows, 6--7 sheep, 3 geese | 5--14 cows, 3--13 sheep, 0--4 geese according to the game |
| Crop transition | 33 strawberries; carrots mainly from day 24 | About 28 strawberries; carrots ramp gradually from day 14 |
| Labor | Variable, sometimes 12 | Stable 11 hands on days 10--27, then 10 |
| Terminal phase | Some care/feed remains on day 29 | Strong day-28/29 contraction and liquidation |

## Recommended search-space changes

Priority order:

1. Search a **multi-turn opening genome** covering the first 24 actions.  Include
   asset purchases, hires, seed purchases, and one-unit product trades, rather
   than optimizing only `_R42_OPENING`.
2. Add a **day-6 animal allocation gate** whose inputs are milk/wool price gap,
   current market inventory, existing herd, available pasture and opponent
   herd.  Search cow-heavy, balanced and sheep-heavy target profiles.
3. Add **staged expansion gates** at days 6, 8 and 9, with land/pasture capacity
   tied to the selected herd instead of fixed globally.
4. Search **crop transition gates**: melon exit day 10--12, carrot entry day
   14--20, and lower strawberry targets.  Treat the crop schedule and animal
   feed requirement jointly.
5. Add a **terminal contraction gate** at days 27--29 for hires, animal work,
   remaining crops and liquidation.
6. Search action ordering as short role bundles: animal maintenance -> animal
   collection -> harvest/fertilize -> plant/water -> return/deposit.  Evaluate
   physical execution, not only submitted commands.

The largest lesson is architectural: adding more scalar constants to the old
opening search is unlikely to capture the leader.  The next useful search unit
is a conditional, multi-day trajectory with jointly constrained cash, labor,
land, herd and crop transitions.

## Artifacts

- Replays: `replays/rank1-20260913/`
- Aggregate summary: `reports/rank1_20260913_summary.md`
- Detailed trajectory: `reports/rank1_20260913_decisions.md`
- Cow placement summary: `reports/rank1_20260913_cow.md`
- Current-model comparison trace: `reports/current_20260913_decisions.md`

# Current rank-1 behavior analysis: RuiKimura4

- Collected: 2026-07-31 21:00 JST
- Submission: `55129098`
- Public replays: 17
- Seats: player 0 in 9 games, player 1 in 8 games
- Result: 17 wins / 17 games
- Mean score: 104,794 (median 109,355; range 77,840--119,763)
- Mean margin: +53,151 (median +45,015; minimum +7,452)

Public histories expose submitted actions and public observations, not the
agent source. Market quantities below are requested quantities; affordability
and order processing can make the executed quantity smaller.

## Main finding

The current leader is not a pure cow agent. It runs a deterministic-looking,
three-phase production schedule:

1. Day 0--9: 16 melons + 6 carrots + 2 cows, serviced by 6 hands.
2. Day 10--12: harvest and sell the melons, unlock NE, hire 12 hands, then
   rebuild the farm around livestock and strawberries.
3. Day 13--29: maintain approximately 8--12 cows + 8 sheep + 18 strawberries,
   purchasing wheat rather than dedicating much land to growing feed.

The central cows are important, but the larger advantage appears to be the
whole schedule: early capital generation, an exact Day-10 conversion, dense
routing around the shed, and 12-way parallel servicing.

## Exact opening

Every one of the 17 games submitted the same Day-0 purchases:

- 6 hires
- 16 melon seeds
- 6 carrot seeds
- 2 cows
- 7 wheat over the day

The end-of-Day-0 NW layout was identical in all games (`C` carrot, `M` melon,
`O` cow):

```text
. C C M M
C C M M M
C M M M M
C M M M O
M M M M O
```

The cows are placed at `(4,3)` and `(4,4)`, immediately beside the shed-side
route. Both cows are fed and cared for from Day 0. The carrots are harvested
and sold on Days 3--4; melons are held until the Day-10 conversion.

## Day-10 capital conversion

The common transition is:

- Day 10 hour 1--2: increase from 6 to 12 hands and unlock NE.
- Buy 3 cows and 16 strawberry seeds immediately.
- Harvest the 16 mature melon tiles using the 12 units.
- Submit about 420 melon sales in the day.
- Buy another 3 cows around hour 15.
- Use the melon proceeds to continue purchasing cows/sheep and building
  pastures through Days 10--12.

Average money rises from about 4,253 at the start of Day 10 to 19,521 at the
end, despite the land, livestock, seed and hiring costs. This one-day liquidity
event funds the final farm.

At the end of Day 10, six cow positions are invariant across all games:
`(4,3)`, `(5,3)`, `(3,4)`, `(4,4)`, `(5,4)`, `(6,4)`. These form a compact
block around the central shed-access area. Day 11 extends the block upward and
sideways.

## Mature farm

By Day 13--15, the observed average profile is:

| Resource | Average |
|---|---:|
| Hands | 12.0 |
| Pastures | 18.6 |
| Cows | 10.6 |
| Sheep | 8.0 |
| Strawberries | about 18 |

The cow count is state-dependent: five games ended at 8 cows, three at 11,
and nine at 12. All variants retain the same mixed-production structure.
The simple previously tested rule based only on the Day-10 milk/wool price
does not explain this branching (2/17 classification accuracy). It may depend
on richer market/town/opponent state or on execution progress.

Eight central cow cells are invariant in the mature layout:
`(3,2)`, `(4,2)`, `(4,3)`, `(5,3)`, `(3,4)`, `(4,4)`, `(5,4)`, `(6,4)`.
Higher-cow variants add `(5,2)`, `(6,2)`, `(7,3)` and sometimes `(2,3)`.
Only NW and NE are unlocked; no money or travel is spent on the bottom half.

## Operating pattern

- Wheat is bought as operating input: roughly 18.5 units/day in the stable
  phase, closely matching the 18.5 livestock average.
- Every animal is normally fed daily. Care is also close to once per animal
  per day, except on heavy harvest days.
- Fertilizer is mostly collected and sold; a small amount is used on
  strawberries from about Day 19 onward.
- Milk and wool sales are staggered instead of blindly liquidating everything
  every turn.
- Strawberry harvest workload temporarily reduces care/collection on Days 23
  and 27, showing an explicit cyclic schedule rather than purely greedy task
  selection.
- At Day 27 the agent begins selling surplus wheat, and watering winds down as
  the season ends.

## Difference from the current `main.py`

The current agent uses an opening sheep strategy and switches at Day 8 to a
target of 15--16 cows, 4 sheep, 2 wheat tiles, and 11 hands. The leader instead:

- starts 2 cows on Day 0;
- keeps the melon opening until Day 10;
- uses 12 hands;
- targets fewer cows (8--12) but more sheep (8);
- preserves about 18 strawberry tiles after conversion;
- buys feed rather than using much prime land for wheat.

Therefore, copying only the leader's cow coordinates or raising `COW_TARGET`
is unlikely to reproduce its strength. The first candidate worth testing is
the complete Day-0/Day-10 schedule, with the 8/11/12 cow count treated as a
separate decision variable.

## Recommended experiments

1. Reproduce the exact Day-0 layout and verify that 16 melons can be harvested
   and sold on Day 10 with 12 hands.
2. Implement a fixed conservative mature profile first: 8 cows, 8 sheep,
   16--18 strawberries. This is the variant least likely to overload routing.
3. Search the Day-10 branch among 8, 11 and 12 cows using the fast runner,
   while holding the layout and routing constant.
4. Compare purchased-wheat feeding against the current two wheat tiles.
5. Promote only after fast/standard parity and head-to-head tests against the
   current `main.py`, Pulse, score800, and the public rank-1 replay-derived
   opponent set.

## Generated evidence

- `reports/rank1_latest_summary.md`
- `reports/rank1_latest_cow_analysis.md`
- `reports/rank1_latest_adaptation.md`
- `reports/rank1_latest_games.csv`
- `replays/rank1_latest/manifest.json`


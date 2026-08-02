# Expert replay and public-notebook mining for Kaggriculture

Date: 2026-08-02

## Conclusion

Public expert behaviour should determine the option space before reinforcement
learning is expanded.  Kaggriculture has several strong but qualitatively
different strategy families.  A selector trained over one hand-designed list of
scalar adjustments will miss this structure and will tend either to copy the
incumbent (`KEEP`) or to combine incompatible choices.

The recommended order is:

1. collect recent public episodes from the current top teams;
2. extract sparse strategic change points and the observable state before them;
3. inspect strong public notebooks to recover the intended conditional logic;
4. implement coherent, licensed continuation modules;
5. counterfactually evaluate every module from identical saved states;
6. only then train the recurrent option-value selector.

The leaderboard and public episodes change over time.  The concrete findings
below use repository snapshots collected on 2026-07-31 and must be refreshed
before a promotion decision.

## What the current evidence already shows

### Current rank-1 snapshot: conditional livestock specialization

The ten-game rank-1 study found two repeatable continuation modes using the same
roughly 28 pasture slots:

- cow-heavy: about 22 cows and 6 sheep;
- sheep-heavy: about 12 cows and 16 sheep.

At day 10, the observable rule

```text
MILK >= WOOL -> sheep-heavy
MILK <  WOOL -> cow-heavy
```

matched all ten observed games.  This is much more informative than learning
`COWS_18`, `SHEEP_6`, and similar independent actions.  The expert decision is
a coherent mode switch conditioned on a market relationship.

The same episodes show a staged program:

- days 0-1: around 11-12 melons, 2 sheep, and 3 workers;
- days 2-6: carrots are used as bridge capital;
- days 7-9: about 3 wheat tiles and 3-4 sheep;
- day 10: first major land/livestock conversion;
- days 11-12: labour rises from about 8 to 11 and livestock approaches 28;
- days 18-26: around 12 workers;
- days 27-29: labour is allowed to expire for liquidation.

This indicates that labour, layout, herd size, herd composition, and conversion
day should be represented as one compatible continuation program, not sampled
as unrelated daily actions.

### Rank-2 snapshot: market-intensive balanced livestock

The rank-2 analysis describes a different family:

- two land purchases around days 8 and 11;
- maximum 12 workers;
- roughly balanced cows and sheep;
- very large wheat buy and sell request volume;
- stronger use of market cycling rather than the rank-1 dense specialization.

This should not be averaged with rank 1 into one policy.  It is a separate
candidate option family whose value depends on the opponent and market path.

### Other top-five snapshots: genuine strategic diversity

The public-history summary also contained:

- large mixed cow/sheep production with extensive care;
- goose/fertilizer-oriented production;
- cow plus strawberry/fertilizer production;
- wheat-heavy market production;
- crop-only production.

Therefore, expert mining should retain several coherent regimes.  The goal is
not to clone the mean top-player trajectory.

## What public notebooks add

Public replays expose executed behaviour but not the author's intended
abstraction.  Public notebooks can reveal:

- phase definitions;
- target herd and crop schedules;
- market-price forecasts;
- opponent-visible-supply estimates;
- reserve and liquidation rules;
- job priorities and routing heuristics;
- which parameters are intended to change together.

The current `main.py` is already derived from the public
"Scenario-Aware Economic Policy" notebook and includes useful low-level
abstractions:

- market pricing and projected demand;
- opponent visible-supply estimates;
- reactive livestock scoring;
- feed-stock protection;
- demand-driven worker hiring;
- land-purchase timing;
- field-job generation and assignment;
- endgame liquidation.

That is evidence against replacing the low-level controller with raw RL.  The
notebook should be treated as a strong execution engine.  Learning should select
or modify higher-level continuation programs around it.

## Source hierarchy

Use evidence in the following order.

### 1. Recent public episodes

Best source for:

- what the submitted agent actually did;
- adaptation across seeds, seats, and opponents;
- the timing of irreversible changes;
- whether a notebook's stated strategy survived implementation.

### 2. Public notebook source

Best source for:

- intended branches and state variables;
- coherent parameter groups;
- reusable low-level modules;
- action legality and implementation details.

Respect the notebook licence and attribution.  Do not copy private or
non-public code.

### 3. Controlled local counterfactuals

Best source for determining whether an observed expert choice is causally useful
for the current agent.  Public correlation alone is not sufficient.

### 4. Leaderboard score

Use only as a filter.  Simulation ratings are noisy and affected by opponent
mix, publication timing, and the currently active submission.

## Proposed option-registry structure

Each option should contain a complete continuation contract rather than one
scalar mutation.

```text
Option
  id
  source and licence
  applicable decision events
  required state features
  schedule program
  spatial/layout program
  market program
  liquidation program
  legality/precondition checks
  mutually exclusive groups
  counterfactual validation metadata
```

Initial families to validate are:

1. `KEEP_CURRENT_PROGRAM`
2. `RANK1_COW_HEAVY_D10`
3. `RANK1_SHEEP_HEAVY_D10`
4. `RANK2_WHEAT_MARKET_BALANCED`
5. `GOOSE_FERTILIZER`
6. `COW_STRAWBERRY_FERTILIZER`
7. `WHEAT_MARKET_HEAVY`
8. `CROP_ONLY_LIQUIDATION`
9. promoted schedule/trajectory genomes from local structured search

These names are hypotheses, not deployment-ready policies.  Each requires an
explicit implementation and same-state counterfactual evaluation.

## Decision events to mine

Do not force one decision per day.  Candidate events include:

- first shop unlock affecting the current production mix;
- milk/wool or crop-price ordering change;
- land becomes affordable with operating reserve remaining;
- planned field conversion begins;
- herd capacity or feed burden crosses a threshold;
- opponent visibly commits to a production family;
- shed-pressure or price opportunity triggers realization;
- liquidation horizon is reached.

The new `scripts/mine_expert_options.py` extracts replay-visible change points
for land, labour, livestock expansion, crop-to-livestock conversion, and labour
liquidation.  It also records the observable context before each event.

## Important limitations

### Requested market quantity is not executed quantity

Kaggriculture market orders are processed one unit at a time in lockstep.  Large
orders often mean "continue until funds or inventory run out".  Replay action
arguments must not be used directly as purchase/sale labels.

The mining script stores request signatures only.  Exact executed quantities
should later be reconstructed by replaying the official interpreter or by
comparing state transitions with all simultaneous effects accounted for.

### Hidden opponent inventory

Opponent shed, seeds, and carried inventory are private.  Expert triggers may
implicitly depend on inferred hidden stock.  This supports recurrent history
encoding, but it also means a single replay snapshot cannot establish the true
cause of a choice.

### Publication bias

Only public episodes and public notebooks are visible.  A top team may use a
different active private submission.  Refresh the leaderboard and submission
IDs whenever collecting data.

## Implementation consequence

The architecture direction remains a recurrent option-value selector, but its
option descriptors must be generated from expert and locally promoted strategy
modules.  The next engineering task is not PPO integration.  It is:

1. run fresh top-team collection with more episodes;
2. run `scripts/mine_expert_options.py`;
3. inventory strong public notebooks and their licences;
4. create a versioned option registry;
5. implement and test the strongest two or three distinct programs;
6. extend branched counterfactual generation to those programs;
7. train and calibrate the conservative selector.

# Expert replay and public-notebook mining for Kaggriculture

Date: 2026-08-02

## Status of the evidence

Leaderboard snapshots and public submissions change quickly.  The 2026-07-31
rank-one/rank-two notes in this repository are historical evidence, not the
2026-08-02 ranking.  They remain useful as distinct strategy families, but they
must not be labelled as the current leader without a fresh authenticated
leaderboard download.

The newest supplied public notebook provides stronger architectural evidence
than another hand-written list of scalar options.  It distils Kaito Fukami's
side of public episode 89454731 into an executable 720-turn tape.  The source
trajectory scored 125,364 against venks' 128,733, so the tape came from the
losing side of that particular game.  Nevertheless, the frozen schedule was
competitive across many other seeds, opponents, and both seats.

This separates two quantities that earlier analysis sometimes conflated:

- source-game outcome;
- counterfactual robustness of the complete schedule.

## What the 2026-08-02 notebook shows

### The submitted policy is almost entirely time indexed

The generated agent returns the action stored for `obs.step`.  It does not read
live prices, weeds, inventory, the opponent, or the current board when choosing
its nominal command.  Its performance therefore comes from the quality of the
full timed production program rather than a sophisticated online policy.

### The useful unit is the complete supply-chain schedule

The distilled trajectory couples:

- day-0 purchase of three cows, one sheep, and six melon seeds;
- a small melon opening rather than permanent melon monoculture;
- progressive rotation into roughly forty strawberry tiles;
- first and second extra-land purchases around days 8 and 11;
- labour growth to twelve hands;
- a final mixed herd of about eight cows and seven sheep;
- repeated wheat acquisition and product liquidation;
- gradual crop contraction and labour expiration near the end.

These choices are not safely separable.  Crop count changes alter watering and
harvest work; herd changes alter feed, care, fertilizer, market, storage, and
route demands; land timing changes geometry; labour timing changes whether all
of the above can be executed.

### More adaptation can reduce wins

The notebook tested a small early cash router.  It improved one counter-family
mean margin but reduced wins, so it was rejected.  This is evidence against
adding a learned switch at every apparent strategic event.  A locally sensible
change can invalidate the remaining tape.

### Fixed-trace stress tests are useful but not a real responsive league

The notebook evaluates candidates against preserved public action traces.  This
is a valid comparative stress test because each candidate sees the same replay
mechanism.  It is not proof that a live opponent would keep taking the same
actions after our behaviour changed.

### Requested market quantities are not execution labels

The tape contains very large wheat buy and sell requests.  Kaggriculture orders
are processed unit by unit and may stop due to funds, inventory, or capacity.
Mining code should reconstruct executed transactions or replay the official
interpreter before using quantity labels.

## Historical strategy families retained from 2026-07-31

The older public-history snapshots still show genuine diversity:

- dense cow-heavy or sheep-heavy livestock specialization;
- market-intensive balanced livestock;
- goose/fertilizer production;
- cow plus strawberry/fertilizer production;
- wheat-market production;
- crop-only production.

These should remain candidate schedule families.  They should no longer be
represented as independent scalar edits or assumed to reflect the current top
three.

## Revised mining target

The mining pipeline should produce complete, executable schedule records:

```text
Schedule
  stable id and version
  source episode / notebook / local search run
  provenance and licence
  exact action tape or symbolic controller
  day-boundary state anchors
  phase boundaries
  layout and routing assumptions
  market block and liquidation block
  allowed entry days
  commitment horizon
  descriptor vector
  cross-seed / both-seat validation results
```

The default entry day is day zero.  A midgame suffix becomes selectable only
after its asset/layout preconditions and complete suffix have been implemented
and counterfactually tested.

## What to mine from replays

For each public episode, extract:

- exact observations and commands for all 720 turns;
- day-boundary money and productive-asset summaries;
- hands and unlocked quadrants;
- crop, herd, structure, and weed geometry;
- feed requirement and storage pressure;
- requested market orders and reconstructed executed quantities;
- first purchase, expansion, plateau, and liquidation times;
- planned commands that become invalid under untouched seeds;
- deterministic fallback chosen by the existing controller;
- terminal reward under both seats and multiple opponents.

`mine_expert_options.py` remains useful for identifying visible change points,
but its output should feed schedule extraction and repair-trigger analysis, not
a free-switching phase-option policy.

## Revised implementation consequence

The evidence now supports this order:

1. collect fresh top-team public episodes with timestamps and rank snapshots;
2. reproduce rewards and build exact executable tapes;
3. derive symbolic schedules and day-boundary anchors;
4. create the versioned schedule registry;
5. compare complete schedules over identical seeds, seats, and opponents;
6. train a conservative schedule selector at day zero;
7. build deterministic deviation monitoring and RULE_REPAIR;
8. train a state-conditioned residual repair model only on triggered states;
9. add constrained live market-quantity conditioning;
10. consider conservative offline RL only after these supervised layers plateau.

The primary learning problem is no longer "which scalar should change today?".
It is "which complete production schedule should be committed to, and how should
we repair it without destroying its downstream assumptions?"

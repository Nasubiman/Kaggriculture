# Schedule-first learning architecture for Kaggriculture

Date: 2026-08-02

## Final architecture decision

The next learning system should not be a raw 720-turn policy, a daily scalar
parameter editor, or a freely switching library of incompatible midgame
options.  The strongest current evidence supports a schedule-first hierarchy:

```text
versioned executable schedule library
              |
              v
conservative schedule selector
(game start / validated re-entry only)
              |
              v
selected deterministic 30-day program
              |
              +------------------------------+
              |                              |
              v                              v
planned command + reference anchor     live state/history
              |                              |
              +-------- deviation monitor ---+
                             |
                  plan valid and on-track?
                    /                 \
                  yes                  no
                   |                    |
              execute plan     deterministic RULE_REPAIR
                                      |
                                      v
                         learned repair value model
                         may override RULE_REPAIR only
                         with positive confidence bound
                                      |
                                      v
                           legal low-level command
```

Market quantity conditioning is a separate module built after the schedule and
repair layers are validated.  PPO is not the default training method.

## Why the design changed again

The previous revision correctly moved learning above the deterministic
controller, but still described options as phase-level continuation programs
that could be selected at several strategic events.  The latest public notebook
and replay-distillation evidence shows that this is still too permissive.

A high-performing public submission can replay one elite 720-turn action tape
using only `obs.step`.  The source trajectory was not even the winner of its
original game, yet its full capital schedule remained highly competitive over
many other seeds and opponent traces.  The useful object is therefore not an
isolated day-8 herd choice.  It is the coupled sequence of:

- opening animals and premium crops;
- daily labour ramp;
- land purchase timing;
- crop rotation;
- herd expansion and geometry;
- feed acquisition;
- repeated market realization;
- gradual liquidation.

Changing one stage without repairing all later assumptions can destroy the
schedule.  A simple state router added to the fixed tape improved one aggregate
margin but reduced wins, which is direct evidence that more adaptation is not
automatically better.

The architecture now treats a complete schedule as the unit of strategic
choice and reserves learning inside the schedule for local, compatibility-safe
repairs.

## Rule properties that determine the hierarchy

### Partial observation requires history

The opponent's farm and money are visible, but its shed, seeds, and carried
inventories are hidden.  Market inventory is shared and orders are processed
unit by unit in lockstep.  A current snapshot cannot fully identify opponent
stock or intent.  Both the schedule selector and repair model therefore use a
GRU over sparse rule-derived history summaries.

### Terminal cash is the objective

Land, animals, seeds, wheat, and labour reduce current cash while increasing
future production.  Intermediate cash advantage is not a safe dense reward.
Every learned strategic label should be based on final margin or a short-horizon
repair followed by terminal rollout.

### The low-level controller already solves valuable structure

The promoted `main.py` handles legal movement, field jobs, market pricing,
opponent visible supply, feed reserves, land timing, hiring, fertilizer, and
liquidation.  Relearning all of this through raw RL would waste samples and
remove a strong fallback.

### Timing is unusually stable

The board geometry, 30-day horizon, 24-turn daily cadence, growth rules, shop
unlocks, daily worker lifecycle, and endgame deadline are stable.  A timed
schedule can remain useful even when weeds and shared prices vary.  Invalid
commands often fail locally while other parallel commands still execute, so a
well-designed plan can degrade gracefully.

## The four runtime layers

## 1. Executable schedule registry

`training/schedule_registry.py` defines versioned schedule options.  A schedule
must specify:

- stable ID and version;
- family and executable controller reference;
- provenance and licence;
- fixed-width descriptor;
- allowed entry days;
- commitment horizon;
- ordered reference anchors;
- source tags and description.

KEEP must be registry index zero.  The registry has a stable SHA-256
fingerprint, which is stored in model checkpoints to prevent a model from
silently scoring a different option ordering at inference.

Initial schedule families should include:

1. promoted `main.py` / KEEP;
2. Kaito public-tape schedule: small melon opening, strawberry scale, balanced
   eight-cow/seven-sheep herd, three quadrants, twelve hands;
3. rank-one venks public-tape schedule;
4. Radiant market-intensive schedule;
5. current locally promoted EV2 schedule;
6. later schedules distilled from fresh top-three public episodes.

A public tape can be represented either by the exact action sequence or by an
executable symbolic controller distilled from it.  Exact tapes are useful
baselines and teachers; symbolic schedules are preferable for final deployment.

## 2. Conservative schedule selector

`training/recurrent_option_value.py` now explicitly selects whole schedules.
It is run at game start and, later, only at entry points declared compatible by
the schedule registry.  Arbitrary midgame switching is masked by commitment.

The model contains:

- state-summary MLP;
- GRU belief encoder;
- schedule-descriptor MLP;
- state-schedule interaction features;
- bootstrap ensemble value heads;
- KEEP-relative terminal-margin predictions;
- lower-confidence-bound abstention.

It predicts:

```text
final_margin(schedule) - final_margin(KEEP)
```

and chooses a non-KEEP schedule only when:

```text
mean_advantage - lambda * ensemble_std > minimum_advantage
```

The training loss combines Smooth L1 regression, pairwise ranking, bootstrap
masks, and an asymmetric penalty for predicting harmful schedules as
profitable.

## 3. Deviation monitor and deterministic repair baseline

Every schedule has day-boundary reference anchors, such as:

- cash and productive assets;
- hand count;
- unlocked quadrants;
- crop counts;
- cow/sheep/goose counts;
- feed stock;
- shed pressure;
- due jobs;
- planned liquidation progress.

The runtime compares live summaries with the latest anchor.  It does not demand
exact equality.  It produces normalized deviation features and invokes repair
only when one of the following holds:

- the planned command is illegal;
- a required resource is missing;
- an animal is at risk;
- a due harvest/water/feed/care/drop job is being missed;
- worker position drift prevents a planned command;
- storage or market conditions exceed a rule threshold;
- the schedule is materially behind an anchor.

Before learning, a deterministic `RULE_REPAIR` candidate must exist.  Examples
are nearest urgent feed, care, harvest, water, return/drop, or safe PASS.  The
neural repair policy is never the only path to legality.

## 4. Schedule-conditioned repair value model

`training/schedule_repair_policy.py` ranks a small legal candidate set only
when repair is required.  Inputs are:

- recent state history;
- selected schedule descriptor;
- normalized schedule-deviation vector;
- descriptors for legal repair candidates.

Candidate zero is FOLLOW_PLAN.  Each triggered row also identifies a valid
RULE_REPAIR fallback.  Ensemble scores are normalized per row relative to that
fallback.  The model overrides the deterministic repair only when the lower
confidence advantage is positive.  If repair is not required, FOLLOW_PLAN is
executed without consulting the learned ranking.

This boundary is safer than behavior cloning the entire low-level action.  The
network only learns where the fixed schedule or deterministic router is known
to be insufficient.

## Market conditioning

The public tape buys and sells very large quantities of wheat while running a
mixed crop/livestock farm.  Requested quantities are not necessarily executed
quantities because market orders are processed unit by unit and can terminate
when cash, inventory, or capacity runs out.

Do not copy raw order arguments as labels.  Reconstruct executed transactions
or replay the official interpreter.  The market conditioner should preserve the
selected schedule's order and capital intent while adapting only:

- quantity;
- reserve floor;
- feed requirement;
- shed capacity;
- live price and inventory;
- town demand;
- visible opponent exposure;
- remaining horizon.

This module should begin as constrained quantity regression or discrete
quantity-bucket counterfactual selection.  It should not reorder the entire
market block until an ablation proves that reordering helps.

## Training flow

## Stage 0: provenance-safe expert corpus

Collect recent top public episodes and strong public notebooks.  Store:

- retrieval date;
- leaderboard team and rank snapshot;
- submission and episode IDs;
- seat;
- exact observation/action trace;
- source URL and licence/provenance;
- official environment version.

Do not label a replay as the player's private strategy.  Public actions show
executed behaviour only.

## Stage 1: tape extraction and schedule anchors

For every expert episode:

1. reproduce the original reward exactly;
2. extract the 720-turn action tape;
3. compute day-boundary summaries;
4. identify phase changes: opening, first land, labour ramp, crop rotation,
   herd completion, production plateau, liquidation;
5. create reference anchors and a schedule descriptor;
6. replay both seats on untouched seeds;
7. retain schedules with broad robustness, not only high source-game reward.

The source game's result is not the label.  Cross-seed, both-seat performance
is the label.

## Stage 2: full-schedule counterfactual selector

Run each schedule from the same initial seed, seat, and opponent.  Store the
full final-margin vector for every context.  Start selection at day zero.

Only after day-zero selection works should validated early re-entry points be
added.  A schedule may be entered midgame only when:

- its registry declares that day;
- current state passes compatibility rules;
- required assets/layout are available;
- a complete suffix implementation exists;
- counterfactual evaluation includes the same entry condition.

Split train/validation/test by seed and opponent family.  Bootstrap each
ensemble head over whole game contexts.

## Stage 3: repair dataset generation

Generate repair states from three sources:

1. natural drift while replaying tapes under new seeds, seats, and opponents;
2. controlled perturbations of weeds, market paths, worker positions, inventory,
   and missed prior commands;
3. states where the current deterministic controller and a tape disagree.

For each triggered state:

1. enumerate a small legal candidate set;
2. include FOLLOW_PLAN when legal;
3. include deterministic RULE_REPAIR;
4. branch each candidate;
5. continue with the same selected schedule and repair policy;
6. evaluate final margin, or use a validated short horizon followed by a common
   suffix;
7. train advantages relative to RULE_REPAIR.

This is residual learning.  Non-trigger states should remain in the dataset as
negative examples showing that no repair is needed.

## Stage 4: market quantity conditioner

Reconstruct executed quantities and create constrained alternatives around the
schedule's planned market block.  Train from same-state counterfactual terminal
outcomes.  Evaluate separately by seat because lockstep order processing makes
position relevant.

## Stage 5: sequential closed-loop validation

Evaluate the combined system:

```text
select schedule -> execute -> monitor -> repair -> condition market -> finish
```

Use complete games, untouched seeds, both seats, and an opponent league
containing current `main.py`, preserved leaders, public notebooks, and prior
checkpoints.  Report:

- final money and margin;
- win rate with confidence interval;
- worst-opponent and lower-tail margin;
- schedule-selection frequency;
- repair trigger rate;
- learned override rate;
- fallback rate;
- illegal planned-action rate;
- anchor deviation by day;
- per-schedule regret against full counterfactual outcomes.

## Stage 6: conservative offline RL, only if necessary

If supervised full-schedule and repair value learning plateaus, use fitted Q
iteration or another conservative offline method over the sparse hierarchy.
Do not begin with PPO.  Online self-play is the final optional stage and must
retain deterministic fallbacks, opponent mixtures, and rollback gates.

## Promotion gates

No learned layer enters `main.py` until all of the following pass:

1. exact official/fast-runner parity on fixed traces;
2. positive held-out mean margin versus current `main.py`;
3. credible win rate above 50% against current `main.py`;
4. no meaningful regression against every preserved strong opponent;
5. both-seat evaluation;
6. registry fingerprint and schedule implementation validation;
7. no arbitrary switch during commitment;
8. every triggered repair has a legal deterministic fallback;
9. repair model beats RULE_REPAIR, not merely FOLLOW_PLAN;
10. ablation: schedule selection versus one fixed best schedule;
11. ablation: repair model versus deterministic repair;
12. ablation: history versus one-state encoder;
13. ablation: confidence gate versus greedy intervention;
14. lower-tail and worst-opponent risk remain acceptable.

## Implementation in this branch

- `training/schedule_registry.py`
  - versioned whole-schedule schema;
  - reference anchors and normalized deviation;
  - entry/commitment masks;
  - stable registry fingerprint.
- `training/recurrent_option_value.py`
  - whole-schedule GRU value ensemble;
  - KEEP-relative scoring;
  - conservative selection;
  - counterfactual regression/ranking/false-positive loss;
  - checkpoint registry guard.
- `training/schedule_repair_policy.py`
  - schedule-conditioned local repair value ensemble;
  - per-state deterministic fallback anchoring;
  - repair-trigger gating;
  - conservative override.
- `training/test_recurrent_option_value.py`
- `training/test_schedule_architecture.py`

The old flat-slice Transformer and daily 18-action PPO path should remain
retired.

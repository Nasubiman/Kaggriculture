# Rule-first recurrent option-value architecture

## Revised conclusion

The original proposal on this branch was a small Transformer that split the
legacy 102-dimensional hybrid-PPO observation into arbitrary contiguous blocks
and preserved the old 18-way daily action head.  After reviewing the official
game rules, the current promoted `main.py`, and the repository's completed
experiments, that design is not the right next step and has been removed.

The correct learning boundary is not "choose one parameter edit every day".
It is:

> At a small number of strategically meaningful states, choose among coherent,
> legality-tested continuation programs, or abstain and keep the incumbent.

The new implementation is `training/recurrent_option_value.py`.

## Rule properties that determine the architecture

### 1. The game is partially observed

Both farms, money, tiles, worker positions, market, and town shops are public.
The opponent's shed, seeds, and per-worker inventories are private.  Therefore
a single state snapshot is not Markov from the agent's perspective.  Opponent
intent and hidden stock must be inferred from history: visible plantings,
placements, harvest timing, market inventory changes, purchases implied by
farm changes, and worker behaviour.

A feed-forward one-snapshot policy discards this information.  The proposed
model therefore encodes a sequence of sparse decision snapshots with a GRU and
uses its final hidden state as a belief representation.

### 2. There are 720 turns, but only a few true strategic decisions

The official game has 30 days and 24 turns per day.  Low-level play includes
movement, watering, harvesting, feeding, care, fertilizer collection, shed
routing, and up to ten market orders every turn.  The current scripted agent
already handles these constraints and has been heavily optimized.

Exposing those 720-turn actions to RL would create a huge structured action
space, waste samples relearning legality and pathfinding, and remove the safe
fallback.  Learning remains above the existing controller.

Useful decision points are event driven, for example:

- first land-expansion opportunity;
- livestock conversion / herd expansion;
- each new shop unlock;
- meaningful milk/wool or crop price regime changes;
- labour-capacity shortages;
- storage pressure;
- start of liquidation.

Fixed daily decisions should be retained only as a simple initial data schedule,
not as the final control abstraction.

### 3. Final money is the true reward

The terminal reward is final cash.  Intermediate money difference is not a
valid dense value target because buying land, animals, seeds, wheat, or labour
reduces cash while increasing future production.  The old PPO shaping based on
money advantage can therefore punish correct investment.

The strongest existing result instead comes from branching the exact same
state into multiple continuation profiles and observing final margins.  This
produces direct counterfactual targets for the decision that matters.

### 4. Market interaction is simultaneous and path dependent

SELL and BUY orders are processed one unit at a time in lockstep.  Both players
receive the same pre-commit quote for each unit, after which shared inventory and
price change.  Town demand also changes inventory during the season.  A useful
state representation must include price/inventory trajectories and visible
opponent production, not only current prices.

### 5. Daily reset makes strategy naturally hierarchical

Workers disappear each day, inventories are automatically dropped to the shed
up to capacity, worker positions reset, plants and animals refresh, weeds spawn,
and shops may unlock.  This creates three natural timescales:

1. season-level program: layout, crop/livestock regime, land timing;
2. phase/event-level option: targets and economic response for the next phase;
3. turn-level execution: the existing deterministic router and market planner.

The learner belongs at level 2, conditioned on level 1 and executed through
level 3.

## Evidence from the repository

The daily semantic PPO prototype generated 1,864 complete games across its
main experiments.  With the teacher prior active it collapsed to KEEP; removing
the prior exposed interventions that were worse than the incumbent.

By contrast, counterfactual value learning evaluated several continuation
profiles from identical live states.  The scaled experiment used 7,000 decision
states and about 66,000 state/profile outcomes.  Its day-8 selector reached a
70% win rate and +613 mean margin against the then-current `main.py`, while
retaining large wins against weaker references.

Hierarchical structured search also succeeded by changing coherent policy
regimes rather than isolated daily edits.  These results indicate that better
labels and better option semantics matter more than replacing the MLP with a
larger generic encoder.

## Proposed control architecture

```text
Official observation history
        |
        v
Rule-derived structured summaries at decision events
        |
        v
GRU belief encoder  --------------------------+
        |                                      |
        v                                      v
current belief                         candidate option descriptors
        |                                      |
        +-------- option-conditioned scorer ---+
                           |
                           v
              ensemble advantages vs KEEP
                           |
                           v
        lower confidence bound + legality mask
                           |
                 choose option or KEEP
                           |
                           v
      existing scripted low-level controller
```

### State history

The first implementation can reuse and extend the counterfactual feature set,
but each decision record should include deltas since the previous event:

- day/hour and time remaining;
- own/opponent public farm composition by crop/animal;
- land and visible worker capacity;
- own private shed, seeds, and carried inventory;
- market price and inventory for every product;
- price/inventory changes over recent events;
- unlocked shops and newly unlocked shop;
- feed requirement, storage pressure, due workload, and liquidation pressure;
- current schedule, spatial trajectory, and active strategy family;
- visible opponent changes since the previous event.

Raw 10x10 tile tokens are not the first priority because the existing planner
already converts spatial state into roles, workload, route lengths, and
capacity.  Tile or quadrant encoders should be added only if ablations show
that these rule-derived summaries lose information relevant to option ranking.

### Options

An option is a coherent continuation program, not one scalar mutation.  Initial
options should be generated from already validated sources:

- KEEP the current promoted program;
- top structured-search genomes;
- top daily schedule genomes;
- top spatial trajectory genomes;
- counterfactual macro profiles and useful combinations;
- explicit market-response or liquidation modules.

Every option needs:

- a stable name and version;
- a feature descriptor used by the network;
- applicability and legality rules;
- deterministic code that installs it on a fresh agent module;
- a defined duration or termination event;
- tests that distinguish it from KEEP and from other options.

Continuous free-form parameter generation is postponed until the discrete
option library is well covered.  A generative policy would otherwise exploit
invalid, inactive, or destructive parameter combinations already encountered
in earlier work.

### Model

`RecurrentOptionValueNet` contains:

- state MLP stem;
- GRU over the sparse decision-history sequence;
- option descriptor MLP;
- option-conditioned interaction features
  `[belief, option, belief*option, abs(belief-option)]`;
- several independent value heads.

Each head predicts final-margin advantage relative to KEEP.  KEEP is made
exactly zero by subtracting its raw score from all options per head.  This
anchors training and removes the need to estimate an arbitrary absolute game
value accurately.

### Conservative intervention

At inference the model computes:

```text
lower_bound = ensemble_mean - uncertainty_scale * ensemble_std
```

A non-KEEP option is selected only when its lower bound exceeds a configured
minimum advantage.  Invalid options are masked.  Otherwise the controller
abstains to KEEP.

This is more appropriate than a fixed KEEP logit prior: the gate is based on
predicted benefit and epistemic disagreement, not a globally constant bias.

## Training plan

### Stage 1: supervised counterfactual option ranking

Generate shared-prefix branches at selected decision events.  For each context,
run every applicable option to the end of the game and store:

```text
final_margin(option) - final_margin(KEEP)
```

Train with a combination of:

- Smooth L1 advantage regression;
- pairwise ranking loss;
- best-option classification;
- bootstrap-resampled ensemble heads;
- optional asymmetric penalty for false positive interventions.

Split by seed and opponent identity so related states do not leak across train
and validation.

### Stage 2: sequential validation

One-shot branching is insufficient when several options may be chosen during a
game.  Evaluate policies that make decisions at multiple events, with later
choices conditioned on earlier selected options.  Add these trajectories to the
history training set.

### Stage 3: offline / conservative RL only if needed

After the option-value model is strong, fitted Q iteration or another
conservative offline method can propagate value across multiple decision
points.  PPO is not the default because counterfactual full-information labels
are already available and on-policy exploration can easily degrade a strong
incumbent.

### Stage 4: limited online fine-tuning

Online self-play should begin only after the supervised selector passes the
standard-runner gate.  Any online objective must retain:

- a substantial incumbent/opponent mixture;
- KEEP abstention;
- checkpoint league evaluation;
- exact fast/standard runner parity;
- rollback to the promoted deterministic controller.

## Promotion gates

A learned selector should not enter `main.py` unless it passes all of the
following on held-out seeds and both seats:

1. positive mean margin against current `main.py`;
2. statistically credible win rate above 50%;
3. no meaningful regression against every model in `test/`;
4. fast runner and standard runner exact parity on a fixed subset;
5. option-level diagnostics showing no illegal or inactive interventions;
6. ablation proving history helps over a single-state model;
7. ablation proving the uncertainty gate improves downside risk.

## Files on this branch

- `training/recurrent_option_value.py`
- `training/test_recurrent_option_value.py`

The removed flat-slice Transformer and old 18-action checkpoint code should not
be used as the next training path.

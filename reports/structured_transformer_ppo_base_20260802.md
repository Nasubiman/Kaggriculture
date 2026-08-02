# Structured Transformer PPO base

## Goal

The current hybrid policy is a useful safety-first prototype: a deterministic
teacher performs all legal low-level actions and a PPO policy chooses one of 18
masked macro adjustments once per game day.  Its main bottleneck is not PPO;
it is the representation.  A two-layer MLP receives a flat 102-value vector and
must rediscover the relationships between farm state, inventory, market state,
town unlocks, and the active macro strategy.

This branch adds a structured transformer actor-critic without changing the
existing observation, semantic-action, action-mask, or trajectory formats.
That keeps the fast rollout runner, league sampling, reward shaping, and
held-out promotion gates reusable.

## Lessons adopted from Orbit Wars solutions

### 1st place

Use entity/domain tokens, shared attention, learned scratch/global state, and
separate actor/critic heads.  Scaling is valuable only after observation and
action contracts are stable.  Kaggriculture should begin with a small model
because environment throughput and strategy quality are currently more
important than raw parameter count.

### 2nd place

A deliberately restricted action space can outperform a highly expressive one
when it removes low-value exploration.  The existing semantic macro actions are
therefore retained instead of exposing raw worker movement or every purchase.

### 8th place

Factor complex decisions into meaningful stages and use priors rather than a
uniform entropy target.  The current KEEP prior is preserved.  A future version
should factor actions into `decision family -> value/profile -> stop`, allowing
multiple coherent adjustments per day without a combinatorial flat action set.

### 9th place

Use player-relative observations, action masks, a shared self-play policy,
checkpoint leagues, and strict parity tests between training and serving.  The
current Kaggriculture rollout and gate infrastructure already follows much of
this pattern and should be retained.

## Implemented architecture

`training/structured_policy.py` divides the legacy observation into eleven
contiguous domain tokens:

1. time and season phase
2. own farm
3. opponent farm
4. relative score
5. shed inventory
6. seeds
7. carried inventory
8. market prices
9. market inventory
10. unlocked shops
11. current macro strategy

Every block has its own small MLP projection.  Learned token-type embeddings and
a CLS token are added, followed by a pre-norm Transformer encoder.  The policy
head uses one learned query per semantic action, scored against the encoded
state.  The critic reads the CLS representation.

Default size:

- width: 128
- heads: 4
- layers: 3
- feed-forward multiplier: 4
- dropout: 0

This is intentionally small enough for quick PPO iteration on one GPU.  It can
be scaled only after passing the existing incumbent and strong-reference gates.

## Compatibility

The new model keeps the callable contract:

```python
logits, value = model(observations)
```

where observations have shape `(batch, 102)`, logits have shape `(batch, 18)`,
and value has shape `(batch,)`.  Existing action masks and categorical PPO loss
can be used unchanged.

Structured checkpoints use policy version 3 and architecture tag
`structured_transformer_v1`; they are kept separate from legacy MLP policy
version 2 checkpoints to prevent accidental loading.

## Validation

`training/test_structured_policy.py` checks:

- token slices cover all 102 features exactly once;
- output shapes and values are finite;
- masked categorical PPO loss backpropagates through the model;
- checkpoint save/load is numerically identical.

Run from the repository root with:

```bash
PYTHONPATH=training python -m unittest training.test_structured_policy -v
```

## Recommended next implementation steps

1. Add a model factory to the rollout worker so both legacy and structured
   checkpoints can be selected by checkpoint metadata.
2. Train the structured model with the existing one-action-per-day contract to
   isolate representation gains.
3. Replace the flat 18-way head with an autoregressive macro action sequence:
   `STOP/KEEP`, family, then family-specific value.  Limit the sequence to
   three micro-actions per day and apply masks after every choice.
4. Add policy KL to the deterministic teacher early in training, then anneal it.
   A fixed KEEP cross-entropy term is less informative than distillation over
   state-dependent teacher choices.
5. Build a league from promoted structured-search genomes and past neural
   checkpoints.  Sample difficult opponents with PFSP, but reserve a fixed
   fraction of games for the current incumbent.
6. Promote only after fixed-seed, both-seat Arena evaluation against every model
   in `test/`, with parity checks through the standard runner.

## Reward recommendation

Keep terminal win/loss as the primary objective.  Potential shaping should be
based on changes in an economic value estimate rather than money alone:

- cash
- inventory marked to current market value
- productive animal/crop assets
- unlocked land
- expected remaining-season production

Anneal shaping to zero.  This reduces early sparse-reward difficulty without
letting the policy optimize an imperfect proxy indefinitely.

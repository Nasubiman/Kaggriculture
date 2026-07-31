# Counterfactual GPU value-learning trial

Date: 2026-07-31  
Host: `kag-server`

## Outcome

A counterfactual macro-profile value model now trains on GPU and can be used
as a day-8 policy in held-out Arena games. The final corrected experiment beat
the current deterministic `main.py` on unseen seeds:

| Evaluation | Games | Wins | Ties | Win rate | Mean margin |
|---|---:|---:|---:|---:|---:|
| fast runner, unseen 200 seeds/both seats | 400 | 241 | 56 | 60.25% | +237.18 |
| standard runner parity subset | 40 | 30 | 0 | 75.0% | +54.8 |

The same 40 games matched exactly between the fast and standard runners,
including selected profile, rewards, margins, and status.

This is a successful research candidate, not yet a submission promotion. The
mean margin is positive but small, and the candidate has only been gated
against `main.py`, not the score-800 reference, Pulse, or public-leader
proxies.

## Pipeline

1. `training/generate_macro_counterfactuals.py` evaluates 23 macro profiles
   from the same day-8 state for each seed and seat.
2. `training/train_counterfactual_value.py` groups those games into complete
   state-by-profile matrices.
3. A GPU MLP predicts each profile's final-margin advantage relative to
   `KEEP`. It trains with Smooth L1 regression, pairwise ranking, and best
   profile classification losses.
4. `training/evaluate_counterfactual_value.py` loads the checkpoint, selects a
   profile at day 8, and runs held-out both-seat Arena games.

The checkpoint records feature normalization, profile names, architecture,
weights, and training metadata. The final local copy is under
`server-results/counterfactual_value_v3/best.pt`.

## Correctness issue found

The first experiment revealed that `main.py`'s internal day-8 learned profile
ran after the external counterfactual choice. It silently overwrote cow and
wheat profile values, so several apparent actions were actually aliases of
`KEEP`.

The generator and evaluator now resolve the internal default first, disable
that hook for the episode, and then apply the explicit profile. A smoke test
confirmed that `COW_14`, `COW_15`, `COW_17`, `COW_18`, and `WHEAT_4` produce
distinct outcomes. The final model and reported result use corrected data.

## Final training data and model

- 100 new seeds;
- both seats;
- 23 profiles;
- 4,600 complete games;
- 200 unique decision contexts;
- 160 training and 40 validation contexts;
- 34 state features;
- 256-wide, three-hidden-layer value model;
- best epoch: 120;
- GPU training time: 4.03 seconds;
- peak allocated GPU memory: 23.96 MB.

Offline validation:

- top-1 oracle-profile accuracy: 62.5%;
- zero-regret rate: 62.5%;
- mean regret: 291.6 margin;
- selected-profile mean advantage over `KEEP`: +822.5 margin;
- oracle mean advantage: +1,114.2 margin.

## GPU interpretation

The GPU pipeline works, and two model/loss variants were also trained
concurrently on GPU 0 and GPU 1 during the prototype. However, 200 contexts
and a sub-million-parameter MLP are still too small to keep either RTX 2080 Ti
busy. The final fit takes four seconds and allocates only about 24 MB.

The useful scaling path is more decision contexts and more decision days, not
artificially increasing epochs. A dataset with tens or hundreds of thousands
of state/profile rows can use large batches and mixed precision effectively.
Prefix-state snapshotting should be implemented before that scale so every
profile does not replay days 0-8 independently.

## Reproduction

```bash
make server-counterfactual-generate \
  CF_DATA=/media/deepstation/storage/nakamura_y/kaggriculture/datasets/counterfactual/my_data.json \
  CF_SEEDS=100

make server-counterfactual-train \
  CF_DATA=/media/deepstation/storage/nakamura_y/kaggriculture/datasets/counterfactual/my_data.json \
  CF_RUN=/media/deepstation/storage/nakamura_y/kaggriculture/runs/my_value_run

make server-counterfactual-evaluate \
  CF_RUN=/media/deepstation/storage/nakamura_y/kaggriculture/runs/my_value_run
```

## Next gate

Before integrating this selector into `main.py`:

1. run at least 400 both-seat games against the score-800 reference;
2. run the same gate against Pulse and the strongest available incumbent;
3. repeat with a completely separate seed block using the standard runner;
4. require positive mean margin as well as a win rate above 50%;
5. export the selected model to a submission-safe NumPy implementation only
   after all gates pass.

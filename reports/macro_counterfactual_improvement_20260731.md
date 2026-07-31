# Counterfactual macro-policy improvement

Date: 2026-07-31  
Compute host: `kag-server`

## Outcome

The current deterministic `main.py` was improved with a one-shot learned
macro decision at the start of day 8. The implemented candidate beat the
previous `main.py` in 151 of 200 completely held-out games:

| Candidate | Opponent | Seeds | Games | Wins | Win rate | Mean margin |
|---|---|---:|---:|---:|---:|---:|
| learned macro tree | previous `main.py` | 100 | 200 | 151 | 75.5% | +541 |
| learned macro tree | `pulse_breaker_v2.py` | 30 | 60 | 60 | 100% | +72,697 |

Every seed was played from both seats. All large evaluations ran on
`kag-server`; local execution was limited to syntax checks and small smoke
tests.

## Why the previous PPO design was changed

The previous hybrid PPO policy made one of 18 persistent macro changes on
every in-game day. That produced 30-step credit assignment even though most
parameters should only be selected once. The teacher prior then drove the
deterministic policy to `KEEP`, while removing the prior produced repeated,
harmful interventions.

The replacement formulates the problem as a contextual one-shot decision:

1. run the strong scripted policy unchanged through the opening;
2. observe the public game state at day 8, hour 0;
3. select one repeat-safe macro profile;
4. let the scripted router execute the remaining 22 days.

This produces direct counterfactual labels and can later be used to
behavior-clone a selector before PPO fine-tuning.

## Counterfactual dataset

The first server scan evaluated 23 profiles over 30 seeds and both seats:

- 1,380 complete games;
- the old `main.py` was the opponent in every game;
- every profile saw the same state distribution before the day-8 decision;
- features include market prices/inventories and both public farms.

Top universal profiles in this scan:

| Profile | Games | Wins | Win rate | Mean margin |
|---|---:|---:|---:|---:|
| wheat plots 3→2 | 60 | 43 | 71.7% | +131 |
| cows 16→15 and wheat 3→2 | 60 | 40 | 66.7% | +477 |
| cows 16→15 | 60 | 38 | 63.3% | +227 |

An independent 50-seed/100-game validation reproduced the result:

| Profile | Games | Wins | Win rate | Mean margin |
|---|---:|---:|---:|---:|
| wheat plots 3→2 | 100 | 80 | 80.0% | +18 |
| cows 16→15 and wheat 3→2 | 100 | 73 | 73.0% | +601 |
| cows 16→15 | 100 | 65 | 65.0% | +443 |

## Learned policy

A shallow policy tree was fitted only on the initial scan and selected using
the 50-seed validation set. It always uses two wheat plots after day 8, then
chooses 15 or 16 cows:

```text
if CARROT market inventory <= 9,975:
    target 15 cows
elif WHEAT price <= 34:
    target 16 cows
else:
    target 15 cows
```

The features are public and available directly in the competition
observation. The profile is reset at day 0 so repeated local Arena games do
not leak module state.

The final 100-seed/200-game direct evaluation used a fourth, untouched seed
set. The candidate was loaded from the actual modified `main.py`, while the
opponent was loaded from the previous server `main.py`.

## Artifacts

- generator: `training/generate_macro_counterfactuals.py`
- implementation: `main.py::_apply_learned_macro_profile`
- server run:
  `/media/deepstation/storage/nakamura_y/kaggriculture/runs/macro_counterfactual_v1`
- local copies:
  `server-results/macro_counterfactual_v1/`

## Next learning step

The 23-profile counterfactual table is a better initialization source than
the old analytic `KEEP` prior. The next PPO iteration should:

1. make only one macro decision at day 8;
2. behavior-clone the best counterfactual profile for each state;
3. start PPO from those logits rather than a fixed `KEEP` bias;
4. use an incumbent Arena gate on new seeds;
5. expand the profile set only after the selector beats this tree.

This keeps PPO focused on the remaining conditional decision instead of
relearning movement, legality, and livestock routing.

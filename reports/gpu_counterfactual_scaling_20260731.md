# GPU counterfactual scaling experiment

Date: 2026-07-31  
Host: `kag-server` (2 × RTX 2080 Ti)

## Result

The counterfactual value-learning pipeline was scaled from one day and 200
decision states to five decision days, multiple opponents, 7,000 states, and
about 66,000 state/profile outcomes. The final opponent-conditioned model
improved the current `main.py` without sacrificing its large lead over Pulse
or the score-800 reference.

| Gate | Games | Wins | Ties | Win rate | Mean margin | KEEP delta |
|---|---:|---:|---:|---:|---:|---:|
| main, decision day 8 | 200 | 140 | 30 | 70.0% | +613.28 | +613.28 |
| main, decision day 24 | 200 | 179 | 4 | 89.5% | +276.33 | +276.33 |
| Pulse, decision day 8 | 100 | 100 | 0 | 100% | +70,495.12 | +169.43 |
| Pulse, decision day 24 | 200 | 200 | 0 | 100% | +72,636.69 | +701.90 |
| score800, decision day 8 | 100 | 100 | 0 | 100% | +73,085.96 | +167.04 |
| score800, decision day 24 | 200 | 200 | 0 | 100% | +75,256.24 | +702.02 |

The day-8 policy has the largest improvement against the current strongest
incumbent. The day-24 policy is more conservative and produces a higher win
rate through smaller late-game improvements.

A 40-game standard-runner subset for the final day-8 model matched the fast
runner exactly on selected profile, rewards, margin, and status. It won 37/40
with mean margin +798.65.

## Data generation

`training/fast_kaggriculture.py` now supports interval execution and live-state
cloning. `training/generate_branched_counterfactuals.py` runs the common prefix
once and branches the same official state at days 8, 12, 16, 20, and 24.

The branched generator matched the original full-episode generator exactly in
a same-seed, both-seat, multi-profile comparison.

Generated data:

- main opponent, 200 seeds, 13 profiles: 2,000 states / 26,000 outcomes;
- main opponent, additional 400 seeds, 8 profiles: 4,000 states / 32,000 outcomes;
- Pulse, 50 seeds and five days: 500 states / 4,000 complete games;
- score800, 50 seeds and five days: 500 states / 4,000 complete games.

Total: 7,000 decision states and approximately 66,000 profile outcomes.

Arbitrary external opponents cannot safely use snapshot branching because a
freshly loaded stateful agent may have hidden Python state that is not present
in the official environment state. Pulse and score800 data were therefore
generated as complete day-0 episodes. The branched generator rejects non-Python
opponent sources rather than silently producing invalid continuations.

## GPU changes

The trainer now supports:

- FP16 automatic mixed precision;
- batches up to 1,024 in the measured runs;
- seed-grouped train/validation splitting;
- independent validation datasets;
- multi-file datasets with a common profile subset;
- two-GPU architecture and loss sweeps;
- elimination of per-minibatch CPU synchronization.

The final model uses six 2,048-wide hidden layers. Training characteristics:

- training contexts: 5,600;
- validation contexts: 1,400;
- validation top-1 accuracy: 78.2%;
- validation zero-regret rate: 78.4%;
- validation mean regret: 194.5 margin;
- selected-profile mean advantage: +350.3 margin;
- GPU peak allocation: 509.8 MB;
- GPU training time: 19.2 seconds;
- complete process time after initialization optimization: 22.6 seconds.

The original orthogonal initializer performed CPU QR decomposition on every
2,048 × 2,048 layer. That made startup exceed three minutes while the GPU
training itself took under 20 seconds. Xavier initialization reduced total
wall time to 22.6 seconds and slightly improved validation regret.

## Opponent conditioning

A model trained only against `main.py` improved self-play but reduced margins
against weak opponents by roughly 4,500 at day 8. The state vector already
contained both farms, so adding Pulse and score800 counterfactuals was enough
to learn different choices for different opponent states.

After mixed-opponent training, day-8 margins improved over KEEP by about +169
against Pulse and +167 against score800 while the main-opponent improvement
increased to +613.

## Artifacts

The 81 MB final checkpoint remains on the server:

```text
/media/deepstation/storage/nakamura_y/kaggriculture/runs/
  cf_multiday_mixed_xavier/best.pt
```

Lightweight metrics and gate outputs are copied to:

```text
server-results/counterfactual_value_multiday/
```

The checkpoint is intentionally not embedded in `main.py`. Submission still
requires distillation to a compact NumPy model or a small decision tree, then
a fresh standard-runner promotion gate.

## Recommended next step

Use the large GPU model as a teacher. Generate its profile labels and value
gaps over all collected states, then distill it into a small network or tree
that can be embedded directly in `main.py`. Gate both day 8 and day 24
students; do not deploy the 81 MB PyTorch checkpoint directly.


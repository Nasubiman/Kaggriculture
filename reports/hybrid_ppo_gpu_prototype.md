# Hybrid PPO GPU prototype

## Status

An Orbit Wars-style hybrid reinforcement-learning pipeline now runs end to end
on `kag-server`. It uses GPU-based PPO updates, CPU-parallel self-play, a
checkpoint opponent league, PFSP-like opponent sampling, legal semantic-action
masks, and held-out Arena evaluation.

The first short experiments did **not** beat the tuned deterministic
`main.py`. No learned checkpoint was promoted and `main.py` was left unchanged.
This is the intended safety behavior of the Arena gate.

## Compute environment

- Host: `kag-server`
- GPUs: 2 × NVIDIA GeForce RTX 2080 Ti, 11 GB each
- Training GPU: device 0
- Rollout workers: up to 16 CPU processes
- Python: 3.12.13
- PyTorch: 2.6.0+cu124
- CUDA runtime: 12.4
- GPU validation: `torch.cuda.is_available() == True`
- Observed PPO peak allocation: approximately 18.6 MB

The neural network is deliberately small, so game simulation remains the
bottleneck and GPU memory use is low. GPU execution was verified with both a
matrix multiplication and PPO gradient updates.

Install the compatible build with:

```bash
.venv/bin/python -m pip install \
  torch==2.6.0 \
  --index-url https://download.pytorch.org/whl/cu124
```

The default PyPI build was CUDA 13 and was incompatible with the server's
current NVIDIA driver. `requirements-gpu.txt` therefore pins the CUDA 12.4
build.

## Architecture

### Hybrid control

The policy acts once at the start of each of 30 in-game days. The existing
deterministic Cow Crown agent continues to execute all 720 low-level turns:

- movement and routing;
- legal farm and market commands;
- feeding, care, harvesting, and dropping;
- final-day collection and selling.

The neural policy receives a 102-element feature vector containing:

- day and season phase;
- public own/opponent farm summaries;
- private shed, seed, and carried inventory;
- market prices and inventory displacement;
- unlocked shops;
- current strategic macro state.

The actor-critic is a two-layer 128-unit MLP with separate policy and value
heads.

### Safe semantic actions

The current action space has 18 masked actions. `KEEP` exactly preserves the
deterministic teacher. Other actions select absolute, repeat-safe profiles such
as:

- commit to cows, delay, or transition earlier;
- target 18 or 14 cows;
- target 6 or 2 sheep;
- use 12 or 10 hands;
- use a wheat-heavy or wheat-lean profile;
- use fast or steady cow purchases;
- use more or less aggressive proceeds estimates;
- collect wheat in batches of 16 or 8.

The first prototype used relative actions such as `MORE_COWS`. Repeating those
actions across days accumulated destructive changes. It was replaced by the
absolute profile action space before the third experiment.

### PPO and league

- clipped PPO objective;
- generalized advantage estimation;
- terminal win/loss plus bounded final-margin reward;
- potential-based money-advantage shaping that decays during training;
- an analytic behavior-cloning prior toward the `KEEP` teacher action;
- scripted opponents: current `main.py`, Pulse Breaker, score800 reference;
- self-play against the current policy;
- past checkpoint league;
- PFSP-like weighting favoring opponents near a 50% estimated win rate;
- a fixed minimum fraction of games against the current `main.py`.

## Experiments

### Experiment 1: relative semantic actions

Run directory:

```text
/media/deepstation/storage/nakamura_y/kaggriculture/runs/hybrid_ppo_orbit_v1_24dd58c
```

- 11 completed updates before early stopping
- 24 games per update
- 264 games
- weak teacher prior

Exploration moved too far from the teacher and performance deteriorated. When
the teacher logit was removed at inference, the learned residual policy made
many compounding changes and lost all development Arena games.

### Experiment 2: strongly anchored relative actions

Run directory:

```text
/media/deepstation/storage/nakamura_y/kaggriculture/runs/hybrid_ppo_orbit_v2_c3c0b28
```

- 30 updates
- 32 games per update
- 960 games
- 28,800 daily transitions
- 40% minimum incumbent games
- constant teacher loss

The policy became stable, but every checkpoint selected `KEEP` on every day in
deterministic Arena evaluation. Removing the teacher prior exposed residual
actions that were worse than the incumbent. The closest checkpoint changed
only to a wheat-heavy profile and still produced a negative mean margin.

### Experiment 3: absolute repeat-safe profiles

Run directory:

```text
/media/deepstation/storage/nakamura_y/kaggriculture/runs/hybrid_ppo_orbit_v3_d51ba34
```

- 20 updates
- 32 games per update
- 640 games
- 19,200 daily transitions
- 50% minimum incumbent games

Without a residual gate, all screened checkpoints selected `KEEP` and matched
the incumbent behavior. With the teacher prior removed, update 16 was the
closest candidate:

- initial development Arena: mean margin -98
- expanded gate evaluation, weakest intervention: mean margin -130.5
- learned intervention: occasional `WHEAT_HEAVY`

Increasing the residual gate caused more wheat-heavy interventions and further
reduced mean margin. The checkpoint was rejected.

Across the three main runs, 1,864 complete games were generated. Smoke tests
and Arena games are additional.

## Reproduction

Check CUDA:

```bash
make server-gpu-check
```

Start a default training run:

```bash
make server-hybrid-train \
  HYBRID_RUN=/media/deepstation/storage/nakamura_y/kaggriculture/runs/my_run \
  HYBRID_ITERATIONS=20 \
  HYBRID_GAMES=32 \
  HYBRID_WORKERS=16
```

Evaluate one checkpoint:

```bash
cd /home/nakamura_y/agriculture/Kaggriculture
.venv/bin/python training/evaluate_hybrid_policy.py \
  --checkpoint /path/to/checkpoints/update_0020.pt \
  --opponents incumbent pulse score800 \
  --score800-reference \
    /media/deepstation/storage/nakamura_y/kaggriculture/datasets/reference/score800_reference.txt \
  --seeds 410011 410023 410037 410049 410061 \
  --workers 8 \
  --output /path/to/arena.json
```

## Interpretation and next steps

The infrastructure works, but the experiment is still orders of magnitude
smaller than top Orbit Wars training runs. More GPU time alone will not solve
the main limitation because Python episode generation is CPU-bound.

The highest-value next changes are:

1. implement a faster vectorized simulator or batch multiple game states;
2. generate counterfactual semantic-action labels and behavior-clone useful
   residual actions instead of cloning only `KEEP`;
3. train from selected decision points rather than forcing one decision every
   day;
4. increase self-play scale only after rollout throughput improves;
5. keep the incumbent Arena promotion gate and require a statistically
   credible win rate above 50% before changing `main.py`.

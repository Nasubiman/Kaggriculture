# Cow Crown 90-minute evolutionary tuning

## Outcome

The current deterministic Cow Crown policy was tuned for 90 minutes on
`kag-server`. The selected candidate beat the pre-training `main.py` in all 20
held-out games and retained a 100% win rate against both local reference
opponents.

No replay files were transferred or used. The search evaluated complete games
directly on the compute server.

## Run

- Date: 2026-07-31 (JST)
- Source commit: `9441457`
- Compute: 16 CPU workers
- Search duration: 5,448.1 seconds (90.8 minutes, including final selection)
- Generations: 85
- Validated candidates: 188
- Run directory:
  `/media/deepstation/storage/nakamura_y/kaggriculture/runs/cow_evolution_90m_9441457`
- Search seed: `20260731`
- Final selection: 18 wins / 18 games
- Final selection mean reward: 89,177.7
- Final selection mean margin: +50,772.4

Command:

```bash
cd /home/nakamura_y/agriculture/Kaggriculture
OMP_NUM_THREADS=1 \
OPENBLAS_NUM_THREADS=1 \
MKL_NUM_THREADS=1 \
CUDA_VISIBLE_DEVICES="" \
.venv/bin/python training/evolve_cow_params.py \
  --minutes 90 \
  --workers 16 \
  --population 20 \
  --shortlist 4 \
  --score800-reference \
    /media/deepstation/storage/nakamura_y/kaggriculture/datasets/reference/score800_reference.txt \
  --output-dir \
    /media/deepstation/storage/nakamura_y/kaggriculture/runs/cow_evolution_90m_9441457
```

## Adopted parameters

| Parameter | Before | After |
|---|---:|---:|
| `COW_START_DAY` | 11 | 8 |
| `COW_TARGET` | 20 | 16 |
| `COW_PURCHASE_BATCH` | 12 | 4 |
| `COW_HANDS` | 12 | 11 |
| `WHEAT_TILES` | 2 | 3 |
| `WHEAT_PICKUP_BATCH` | 8 | 12 |
| `SALE_PROCEEDS_FACTOR` | 0.65 | 0.50 |
| `SHEEP_TARGET` | 2 | 4 |
| `OPENING_HANDS` | 7 | 7 |

## Held-out evaluation

These seeds were not used by the evolutionary quick, validation, or final
selection schedules:

`210011, 210023, 210037, 210049, 210061, 210077, 210091, 210109, 210121, 210143`

Each seed was played from both seats.

| Candidate | Opponent | Games | Wins | Mean reward | Mean margin |
|---|---|---:|---:|---:|---:|
| tuned | pre-training `main.py` | 20 | 20 | 56,591.20 | +28,010.40 |
| tuned | `pulse_breaker_v2.py` | 20 | 20 | 111,799.50 | +70,099.60 |
| pre-training `main.py` | `pulse_breaker_v2.py` | 20 | 20 | 100,976.05 | +64,837.80 |
| tuned | score800 reference | 20 | 20 | 113,355.25 | +72,608.10 |
| pre-training `main.py` | score800 reference | 20 | 20 | 103,461.15 | +68,943.50 |

Relative to the pre-training policy on the same held-out seeds, the tuned
policy increased mean reward by 10,823.45 against Pulse Breaker and 9,894.10
against the score800 reference. This is an offline/local result and does not
guarantee an equivalent Kaggle leaderboard increase.

## Artifacts

Small result files remain on the compute server in the run directory:

- `best_agent.py`
- `best_params.json`
- `metadata.json`
- `search_state.json`
- `selection_results.json`
- `heldout_candidate_vs_incumbent.json`
- `heldout_candidate_vs_pulse.json`
- `heldout_candidate_vs_score800.json`
- `heldout_incumbent_vs_pulse.json`
- `heldout_incumbent_vs_score800.json`

The raw replays were not saved.

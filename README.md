# Kaggriculture agent workspace

This workspace contains a reproducible public-history analysis pipeline and a
self-contained baseline agent for the Kaggriculture simulation competition.

## Setup

```bash
make setup
make kaggle-check
```

Python 3.11 or newer is required. Kaggle credentials stay outside the repository.

## Public Game History

Collect three recent public episodes for each of the current top five teams:

```bash
make history-collect
make history-analyze
```

Replay JSON files are stored under `replays/` and ignored by Git. The generated
strategy summary is written to `reports/public_history_summary.md`.

## Baseline

`main.py` is the directly-submittable Pulse Breaker v2 agent. It:

- uses a deterministic 25-tile diversified crop plan;
- hires seven workers and expands northeast on day 11;
- prioritizes the core farm before expansion tasks;
- harvests six-unit melons from age 10;
- sells melon batches before a clipped-sale opponent can reach the best prices;
- adds fifteen wheat plots after expansion;
- harvests, returns, drops, and sells remaining production on day 30.

Run the fixed-seed, both-seat evaluation:

```bash
make evaluate
make head-to-head
```

Submit after reviewing the generated evaluation:

```bash
.venv/bin/kaggle competitions submit kaggriculture \
  -f main.py \
  -m "history-informed baseline v1"
```

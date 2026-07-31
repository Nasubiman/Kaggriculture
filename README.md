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

`main.py` is a directly-submittable, history-informed rule-based agent. It:

- hires workers aggressively;
- expands land from day 9;
- uses quick wheat/carrot income before diversifying;
- prioritizes endangered plants, harvesting, watering, weeds, then planting;
- delays sales during severe premium-product gluts;
- liquidates inventory near the end of the season.

Run the fixed-seed, both-seat evaluation:

```bash
make evaluate
```

Submit after reviewing the generated evaluation:

```bash
.venv/bin/kaggle competitions submit kaggriculture \
  -f main.py \
  -m "history-informed baseline v1"
```

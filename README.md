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

## Current agent

`main.py` is the directly-submittable Cow Crown v1 agent. It:

- starts with two central sheep to create an early wool income stream;
- preserves and harvests the opening crop cycle before conversion;
- begins the cow transition on zero-indexed day 11;
- expands northeast and builds twenty cow pastures near the shed;
- hires twelve workers for daily feed, care, fertilizer, and harvest routing;
- maintains a wheat buffer through market purchases and two wheat plots;
- rehires workers on day 30 to harvest, return, drop, and sell final output.

The previous crop-only strategy is archived as
`agents/pulse_breaker_v2.py`, and the original baseline as
`agents/baseline_v1.py`.

Run the fixed-seed, both-seat evaluation:

```bash
make evaluate
make head-to-head
```

Submit after reviewing the generated evaluation:

```bash
.venv/bin/kaggle competitions submit kaggriculture \
  -f main.py \
  -m "Cow Crown v1: public-replay cow strategy"
```

See `reports/cow_strategy_implementation.md` for the replay evidence,
parameter search, and held-out results.

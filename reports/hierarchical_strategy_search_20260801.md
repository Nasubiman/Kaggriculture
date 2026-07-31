# Hierarchical strategy search (2026-08-01)

## What changed

The genome is no longer treated as one flat vector. It has five top-level
strategy families:

- `legacy`
- `crop_rotation`
- `land_expansion`
- `market_livestock`
- `hybrid`

Genes are grouped into opening, expansion, livestock, production, endgame,
and layout/service blocks. Mutation and crossover can move whole blocks, while
family-specific inactive genes are ignored. The GPU surrogate receives both a
normalized value and an active/inactive mask for every field. This prevents an
irrelevant parameter from looking like a meaningful difference between two
otherwise identical policies.

Search startup was also changed to recover `_FROZEN_GENOME` from the current
`main.py`. Family anchors are derived from that incumbent, so a run does not
fall back to the historical default policy.

## Five-minute server result

Run: `server-results/structured_20260801_020540`

| Evaluation | Games | Wins | Win rate | Mean margin | Errors |
|---|---:|---:|---:|---:|---:|
| Held-out vs previous `main.py` | 200 | 160 | 80.0% | +569.3 | 0 |
| Fast-runner parity set | 20 | 18 | 90.0% | +1121.5 | 0 |
| Standard-runner parity set | 20 | 18 | 90.0% | +1121.5 | 0 |
| `submission.tar.gz` reference | 200 | 200 | 100.0% | +27643.7 | 0 |

Fast- and standard-runner game records matched exactly on the parity set. The
standalone generated `candidate_main.py` also matched the search-time configured
agent exactly in an additional 20-game check.

The winning family was `crop_rotation`. Its active changes from the incumbent
were:

- sale threshold factor: `0.50 -> 0.45`
- cash layout: `near -> far`
- late wheat target: `18 -> 20`
- final cow target: `7 -> 5`
- final sheep target: `8 -> 6`
- final wheat target: `1 -> 0`

The candidate was promoted to `main.py`. The preceding model is retained as
`main_before_promotion.py` inside the run directory.

## Interpretation

This result supports searching over coherent policy regimes rather than adding
more unrelated scalar gates to a flat genome. The next useful expansion is to
add genuinely different behavioral modules inside each family (for example,
market-response rules or placement planners), while keeping conditional
activation and incumbent-derived anchors.

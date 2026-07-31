# Rank-1-inspired structured gates (2026-08-01)

## Implemented search space

The genome grew from 26 to 52 fields while retaining the old defaults:

- mixed cow/sheep opening;
- staged hand targets;
- first/second land-purchase gates and 1--4 quadrant targets;
- cow, sheep, and goose targets;
- fixed or market-conditioned livestock profiles;
- observed rank-1 central mixed-animal layout;
- middle, late, and end phases with a third transition day;
- independent crop counts, hand targets, and service order for each phase.

The public rank-1 behavior is included as an explicit search anchor. It is not
promoted directly: simulation showed that copying the whole public profile into
the current planner was substantially weaker than the incumbent. Search is
therefore allowed to take only the useful parts.

## Five-minute server search

- Run: `server-results/structured_20260801_005452`
- Population: 32
- Search duration: 5 minutes
- Validated candidates: 72
- GPU surrogate became active from generation 10.

Selected effective changes from the incumbent:

- day 20--26: 10 wheat tiles;
- day 27: a new endgame transition returning wheat target to zero.

The search did not select mixed opening, extra land, geese, or market adaptation
in this short run. Those gates remain available for longer searches.

## Results

| Evaluation | Games | Wins | Win rate | Mean margin | Mean reward | Errors |
|---|---:|---:|---:|---:|---:|---:|
| Held-out vs previous `main.py` | 200 | 185 | 92.5% | +625.4 | 78,801.7 | 0 |
| Fast-runner parity set | 20 | 19 | 95.0% | +711.0 | 84,469.9 | 0 |
| Standard-runner parity set | 20 | 19 | 95.0% | +711.0 | 84,469.9 | 0 |
| `submission.tar.gz` reference | 200 | 200 | 100.0% | +25,261.0 | 83,992.6 | 0 |

Fast and standard results matched game by game. The promoted standalone
`main.py` also matched the configured genome in all eight additional fixed-seed
checks.

The prior saved run also scored 100% against the submission reference, but with
mean margin about +21,539 and mean reward about 74,882. The new selected genome
therefore improved margin and reward on that external gate.

## Promotion

The selected genome was frozen into the root `main.py`. The pre-promotion file
is stored as `main_before_promotion.py`, and the promoted copy as
`promoted_main.py`, inside the run directory.

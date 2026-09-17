# New public opponents, 2026-09-17

Imported the submitted `main.py` from `results (11).zip`, `results (12).zip`,
and `results (13).zip` as `test/results11_20260917`,
`test/results12_20260917`, and `test/results13_20260917`. In each ZIP the
top-level `main.py` has the same SHA-256 as the one inside its submission
archive. The models are distinct files; 11 and 13 are behaviorally very close.

## Important evaluation correction

The previous test-model evaluator optimized the candidate agent by default,
while an unknown opponent model was left unmodified by
`reference_runtime.optimize_reference_agent_module`. That asymmetry changes
trajectories for these models. On the same 10 seeds, unoptimized reciprocal
evaluations gave 12/20 wins for the incumbent and 8/20 for results12; with
optimization the two directions gave 10/20 and 4/20, respectively. The
optimized figures are **not valid evidence** of actual head-to-head strength.

The test-model and matrix evaluators now default to unoptimized agent code;
optimization is an explicit opt-in after model-specific trajectory parity is
verified. Current-genome search likewise defaults to unoptimized code and
records the choice in run metadata. Its previous exploratory results against
these new rivals must be disregarded.

## Correct head-to-head results for unchanged `main.py`

Fast simulator, unoptimized agents, 200 independent seeds × both seats =
400 games per opponent, seed start 39,000,000, zero errors:

| Opponent | Wins | Win rate | Mean margin |
| --- | ---: | ---: | ---: |
| results11 | 237/400 | 59.25% | -1.8 |
| results12 | 271/400 | 67.75% | +163.4 |
| results13 | 237/400 | 59.25% | -3.8 |
| public v45 | 400/400 | 100.00% | +2,636.9 |
| results5 | 396/400 | 99.00% | +6,935.1 |

An earlier, disjoint 100-seed check (seed start 23,000,000) returned 61%,
71%, and 61% against results11–13. The fast and standard Kaggriculture
runners produced identical per-game output on an additional five seeds × both
seats × three new rivals (30 games). This parity check supports the runner,
but is not a confidence interval for the win rates.

Raw files: `current_vs_new_public_raw100_20260917.json`,
`current_vs_new_public_raw200_39m_20260917.json`,
`current_vs_new_public_fast5_20260917.json`, and
`current_vs_new_public_standard5_20260917.json`. The round-robin among the
three new models is in `new_public_matrix_20260917/`; results12 beat 11 and
13 in about 82% of games.

No policy change to `main.py` was made: the existing submission already clears
the requested 50% threshold against each new rival under the corrected
evaluation. Experimental opening and market changes were rejected or left
unpromoted because they were selected under the asymmetric optimizer and/or
damaged performance against the established league.

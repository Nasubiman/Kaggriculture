# Paired win-rate improvement, 2026-09-17

The submitted `main.py` was changed only in its frozen current-genome market
parameters: `wool_sell_hour` 5 -> 22 and `tertiary_sell_hour` 20 -> 15. The
search-selected `opening_prefix` 0 -> 1 was not copied because both opening
families are `inherit`, making that parameter inert. No underlying policy or
simulator code was changed.

## Method

`training/search_win_genomes.py` searched 48 incumbent-centered genomes with
unoptimized (submission-equivalent) agents and the production fast runner.
Results11 and results12 were targets; public v45 and results5 were guards.
The 120-seed held-out search gate selected `offspring_35`, with +10.0 and +5.4
percentage points against the two targets and no guard win-rate loss. The run
is preserved at `server-results/win_genome_new_public_20260917/` locally and
`/media/deepstation/storage/nakamura_y/kaggriculture/runs/win_genome_new_public_20260917/`
on kag-server.

After selection, the actual updated `main.py` and the exact pre-change file
were evaluated on another 200 unseen seeds, both seats (400 games per rival),
seed start 42,000,000. Results13 was not in the search. Each pair used the
same seeds, opponents, and raw/unoptimized agent code.

| Opponent | Before | After | Change | Mean margin change |
| --- | ---: | ---: | ---: | ---: |
| results11 | 218/400 (54.5%) | 249/400 (62.25%) | +31 wins | +154.6 |
| results12 | 296/400 (74.0%) | 310/400 (77.5%) | +14 wins | +97.5 |
| results13 | 218/400 (54.5%) | 249/400 (62.25%) | +31 wins | +154.6 |
| public v45 | 393/400 (98.25%) | 393/400 (98.25%) | 0 wins | -113.6 |
| results5 | 393/400 (98.25%) | 393/400 (98.25%) | 0 wins | +144.9 |

No errors occurred. The v45 margin decreased, though its win count did not;
results12's mean own reward decreased by 74.5 while its margin and win count
improved. This is a win-rate optimization, not a claim of universal reward
improvement.

The updated agent produced exactly the same per-game results in the fast and
standard runners for 5 further seeds x both seats x all three new rivals (30
games). `make submission-build` passed the Kaggle loader validation and built
`submission_fixed.tar.gz`.

Raw independent results:

- `reports/win_genome_candidate_fresh200_20260917.json`
- `reports/win_genome_incumbent_fresh200_20260917.json`
- `reports/win_genome_fast5_20260917.json`
- `reports/win_genome_standard5_20260917.json`

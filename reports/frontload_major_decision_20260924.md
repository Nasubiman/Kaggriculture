# Conditional market frontload, 2026-09-24

The current `main.py` is not a small patch to a single “mixtape” file. Its
documented route-replay chassis selects public Shop Router 0909-family action
tapes, with a Pipe-16 HybridOpening/Metav4-derived controller and many later
reactive layers. The change below targets one such layer, `_v12_frontload`.

## Diagnosis

On 15 clustered seeds that the incumbent often lost, disabling V12 market
frontloading improved wins from 85/180 to 97/180. But on a fresh 60-seed
retest it reduced margins and caused losses against results18 and results20.
The first harmful divergence was a day-6 land/animal purchase turn. After
protecting investment turns, another appeared on a day-12 48-unit wheat
purchase. These are order-dependent cash/inventory transactions, not ordinary
sales.

## Chosen rule

Keep the original V12 frontloading when a market batch contains `BUY_LAND`,
`BUY_ANIMAL`, or at least 20 total `BUY_PRODUCT` units. Otherwise leave its
order unchanged for the later V13 order-book optimizer. This uses only our
own proposed orders, not opponent identity.

## Paired fast-runner evaluation

All comparisons use the same seeds and both seats for both variants. The
first two sets include results18, 20, 23, 24, 25, and 29. The third set
includes results14, 19, 21, 26, and 27; results26 and 27 appear behaviorally
similar, so do not regard these as five independent opponent strategies.

| Fresh seed set | Original V12 | Conditional V12 | Mean margin change |
| --- | ---: | ---: | ---: |
| 120M, 80 seeds | 818/960 | 820/960 | +32.8 |
| 121M, 80 seeds | 818/960 | 826/960 | +24.8 |
| 122M, 60 seeds | 572/600 | 576/600 | +32.9 |

The conditional rule won 14 more of 2,520 paired games across these tests,
with no execution errors. Seat outcomes and related opponents are correlated;
this is evidence of a small, repeatable gain, not a precise statistical
estimate of leaderboard win-rate change. The change was promoted to
`main.py` after the first two fresh sets; the third set evaluated that exact
default against a reconstructed original V12 rule.

`py_compile` and `git diff --check` passed. A five-seed/six-opponent parity
run exactly matched the candidate's fast-runner game records, and
`validate_submission.py` passed a full official episode from both seats.

Data: `frontload_major_holdout80_20260924.json`,
`frontload_major_retest80_20260924.json`,
`frontload_major_diverse60_20260924.json`,
`main_frontload_major_parity5_20260924.json`.

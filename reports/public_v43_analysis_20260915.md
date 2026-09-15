# Public v43 analysis and adoption

Date: 2026-09-15

## Imported opponent

- Model: `test/public_v43_competitive_20260915/main.py`
- Source: `results (9).zip` / `submission_competitive_v43.tar.gz`
- Archive SHA-256: `f76baf851aecc13edefcc640dbf61cd409fd321a719dccb2f1b00559041e4f1e`
- `main.py` SHA-256: `919fc1d61050cd96f799979e49177ae3ac7bce98ec9835724238bea73f4a08ed`
- The loose and archived `main.py` files matched the supplied manifest.

## Baseline result

The pre-v43 incumbent won 58 of 200 games (29.0%) against v43 over 100 seeds and both seats. Its mean margin was -1,625.2 with zero errors.

## What v43 added

The semantic ablation isolated three changes:

1. A shop-pair-specific route family when neither of the first two shops is `YARN_STORE`.
2. A dawn warehouse-overflow guard that sells only cargo whose removal preserves the complete post-dawn warehouse vector.
3. A longer waiting window for already-committed tomato and sheep hires.

The route family was the dominant improvement. In a 30-seed, both-seat ablation, full v43 beat the incumbent by +2,361.9 mean margin, while replacing only its router with the incumbent router reduced the v43-side margin to -282.8. The overflow guard contributed about +106 mean margin in this sample. The longer hiring window was action-equivalent on the tested trajectories.

## Adopted hybrid

The adopted `main.py` uses v43's route family and overflow guard while retaining the incumbent's replay-derived survival guard, frozen current genome, and wool-liquidation overlays.

Held-out results:

| Comparison | Games | Wins | Ties | Losses | Mean margin |
|---|---:|---:|---:|---:|---:|
| Hybrid vs pre-v43 incumbent | 200 | 166 | 0 | 34 | +1,971.6 |
| Hybrid vs public v43 | 100 | 35 | 46 | 19 | +154.2 |
| Pre-v43 incumbent vs public v43, same league seeds | 100 | 14 | 23 | 63 | -2,354.6 |

Against the other league opponents, the hybrid improved mean margin by +2,293 to +2,358 on the same games and did not regress against any tested opponent. The 95% paired confidence intervals for every opponent were strictly positive.

The pre-v43 incumbent is preserved as `test/incumbent_pre_v43_20260915/main.py`. Both it and public v43 are now included in the default current-genome search league.

## Submission validation

`make submission-build` passed isolated compilation, Kaggle-agent loading, a validation episode, and rebuilt `submission_fixed.tar.gz`.

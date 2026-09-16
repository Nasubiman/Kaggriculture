# Public v45 counter-strategy (2026-09-16)

## Source integrity

`results (10).zip` contains `main.py`, `submission_competitive_v45.tar.gz`, and
`v45_manifest.json`.  The direct `main.py`, the archive copy, and the manifest
all agree on SHA-256
`2536d41ed5a00c75204b6350f1c76c54259c774cb065ba2a3a0072eedf210d94`.
The opponent is registered as `test/public_v45_competitive_20260916/`.

## Diagnosis

The previous incumbent won only 5/200 games (2.5%) against v45, with a mean
margin of -1,233.3.  Relative to v43, v45 adds:

- a neutral step-0 WHEAT round trip (`BUY 70`, `SELL 70`); and
- clone-gated market pre-emption when the rival follows the same physical route.

The previous policy retained v43's physical trajectory, so v45's clone detector
was consistently activated.

## Adopted policy

The adopted candidate uses v45's defensive controller, retains the existing
WOOL/STRAWBERRY/WHEAT market genome, and uses this net-13-WHEAT opening:

1. `BUY_PRODUCT WHEAT 45`
2. `SELL WHEAT 45`
3. `BUY_PRODUCT WHEAT 13`

The opening was selected by a multi-opponent search against v45, v43, and
results5, ranked by worst-opponent win rate and then worst mean margin.

## Evaluation

Fixed league, 100 seeds and both seats (200 games per opponent):

| Opponent | Wins | Win rate | Mean margin | Mean reward |
|---|---:|---:|---:|---:|
| public_v45_competitive_20260916 | 197/200 | 98.5% | +1,322.2 | 103,185.4 |
| public_v43_competitive_20260915 | 198/200 | 99.0% | +1,496.9 | 102,209.7 |
| public_v41_competitive_20260914 | 197/200 | 98.5% | +3,270.4 | 102,498.1 |
| public_v41_survival_20260914 | 197/200 | 98.5% | +3,273.8 | 102,496.5 |
| public_v38_low_pressure_20260914 | 200/200 | 100.0% | +30,007.8 | 120,146.4 |
| results5_20260913 | 197/200 | 98.5% | +6,632.9 | 106,493.2 |
| incumbent_pre_v43_20260915 | 197/200 | 98.5% | +3,351.8 | 102,468.1 |

Total league wins improved from 1,189/1,400 (84.9%) to 1,383/1,400
(98.8%).  A larger v45-only check produced 581/600 wins (96.8%), mean margin
+1,511.7, and zero errors.

Submission validation passed in both seats.  The promoted model is stored in
`candidates/v45_multi_opening_q45_20260916/` and in `main.py`.

## Artifacts

- Initial baseline: `reports/incumbent_vs_public_v45_100.json`
- Fixed league: `reports/v45_multi_winner_league100.json`
- 600-game v45 check: `reports/v45_multi_winner_vs_v45_300.json`
- Opening search: `server-results/v45_opening_multi_stage.json`

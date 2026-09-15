# Tertiary market search (2026-09-16)

## Outcome

The incumbent was extended with a third independent product-market gate.  The
adopted candidate keeps the existing WOOL and STRAWBERRY schedules and adds:

- item: `WHEAT`
- active days: 8 through 29
- sell hour: 16
- maximum sale: 6 units per day
- minimum price: 5
- retained inventory: 0

The unrestricted WHEAT liquidation candidate won 199/200 games against v43 but
reduced the candidate's own reward across the league.  It was rejected.  The
capped hour-16 candidate had a positive held-out own-reward confidence bound and
was then evaluated against the full strong-opponent league.

## Held-out v43 search gate

The capped candidate was evaluated over 400 games (200 seeds, both seats):

| Candidate | Win rate | Mean reward | Mean margin | Reward delta | Margin delta | Reward delta 95% lower bound |
|---|---:|---:|---:|---:|---:|---:|
| Incumbent | 98.00% | 99,112.7 | +1,110.4 | — | — | — |
| WHEAT hour 16, cap 6 | 98.50% | 99,185.5 | +1,376.3 | +72.8 | +265.8 | +30.1 |

## Strong-opponent league

Each row contains 200 games (100 seeds, both seats).  Deltas compare with the
previous WOOL-hour-5 plus STRAWBERRY-hour-22 incumbent on the same seeds.

| Opponent | Previous wins | New wins | New win rate | Reward delta | Margin delta |
|---|---:|---:|---:|---:|---:|
| public_v43_competitive_20260915 | 199 | 200 | 100.0% | +58.0 | +528.1 |
| public_v41_competitive_20260914 | 194 | 196 | 98.0% | +55.8 | +500.5 |
| public_v41_survival_20260914 | 194 | 196 | 98.0% | +55.7 | +500.6 |
| public_v38_low_pressure_20260914 | 196 | 196 | 98.0% | +60.9 | +483.4 |
| results5_20260913 | 200 | 200 | 100.0% | +98.0 | +185.8 |
| incumbent_pre_v43_20260915 | 192 | 196 | 98.0% | +67.8 | +505.4 |

There were no simulation errors.  The candidate improved or preserved wins,
mean reward, and mean margin against every league opponent, so it was promoted
to `main.py` and packaged as `submission_fixed.tar.gz`.

## Artifacts

- Search: `server-results/tertiary_market_20260916_v1/`
- Adopted candidate: `candidates/tertiary_wheat_cap6_h16_20260916/`
- League: `reports/tertiary_wheat_cap6_h16_league100.json`
- Rejected unrestricted candidate league:
  `reports/tertiary_wheat_candidate_league100.json`

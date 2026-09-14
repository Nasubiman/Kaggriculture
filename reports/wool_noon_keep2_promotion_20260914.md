# Wool noon liquidation promotion (2026-09-14)

## Change

- Keep the existing `results5_20260913`-based policy and all native routes.
- From day 8 through day 29, sell surplus wool at hour 12 while retaining 2 wool.
- No rank-1 herd-count rewrite was adopted; the direct YARN/herd target candidate regressed badly.

## Held-out league result

The 11-opponent, 60-seed-per-seat final evaluation measured the candidate against
the incumbent on identical episodes:

- mean reward delta: **+32.2**
- 95% lower confidence bound: **+17.7**
- mean margin delta: **+317.0**
- worst opponent margin delta: **+46.4**
- worst opponent reward delta: **-111.3** (`public_v35`, about -0.11%)

Source: `server-results/current_genome_rank1gate_20260914_2000/final_heldout.json`.

## Focused 300-seed comparison

Each row contains 600 games (300 seeds, both seats).

| Opponent | Candidate win rate | Incumbent win rate | Reward delta | Margin delta |
|---|---:|---:|---:|---:|
| `public_v35` | 99.2% | 99.2% | -94.1 | +41.0 |
| `results5_20260913` | 92.8% | 4.3% | +59.0 | +355.9 |
| `incumbent_v37_opening` | 30.5% | 22.2% | +103.9 | +383.2 |

There were zero simulation errors. The candidate passed standalone submission
validation and was promoted to `main.py`; `submission_fixed.tar.gz` was rebuilt.

## Search-gate adjustment

Future searches retain a positive held-out reward confidence bound and require
non-negative average and worst-opponent margin deltas. The per-opponent reward
gate now permits at most a 0.2% relative regression, preventing a strategically
stronger candidate from being rejected for an immaterial absolute score change.

# Current-genome v3 search (2026-09-16)

The incumbent-centered search selected `offspring_37` and promoted it to
`main.py`. The selected genome only changes the tertiary WHEAT liquidation
schedule: `tertiary_start_day` 8 → 14 and `tertiary_sell_hour` 16 → 20. The
item, cap (6), minimum price (5), and all other active policy gates are
unchanged. The frozen runtime also includes the newly available, inactive
opening-roundtrip fields.

## Search and held-out evaluation

- Run: `server-results/current_genome_v3_20260916_run1/`
- Opponents: public v45, public v43, public v41 composition, public v38,
  `results5_20260913`.
- Final search holdout: 200 seeds × two seats × five opponents = 2,000 games
  per finalist. Versus the incumbent, mean own-reward difference was +71.25;
  paired 95% lower bound +40.06. The worst opponent-specific reward difference
  was +37.71. Mean margin difference was +65.46 and the worst opponent-specific
  margin difference was +52.39. No simulator errors were reported.

## Independent league checks

Both checks used seven opponents, 100 seeds, and both seats (1,400 games per
model), with the incumbent and candidate evaluated on the same seeds. The
opponents were v45, v43, v41 composition, v41 survival, v38,
`results5_20260913`, and the pre-v43 incumbent.

| Check | Incumbent wins | Candidate wins | Mean own-reward delta | Mean margin delta | Paired 95% lower bound for own reward |
| --- | ---: | ---: | ---: | ---: | ---: |
| Existing fixed league | 1,383 | 1,384 | +30.87 | +62.80 | +13.13 |
| Fresh seeds (start 22,500,000) | 1,383 | 1,385 | +71.45 | +58.70 | +28.82 |

The fixed league showed a v38-specific reward regression of -29.2 (margin
-8.5), despite an overall gain. On fresh seeds, all seven opponent-specific
reward and margin differences were positive, including v38 (+65.6 reward,
+34.8 margin). Thus the improvement is supported across checks, but the
v38 result on the original seed set remains a caveat. A single-field
`tertiary_sell_hour=20` ablation was weaker against v38 than the selected
two-field candidate.

Raw independent results: `current_genome_v3_candidate_league100.json`,
`current_genome_v3_fresh_candidate_100.json`,
`current_genome_v3_fresh_incumbent_100.json`, and
`current_genome_v3_hour20_only_league100.json` in this directory. The search
run contains `decision.json`, `best_genome.json`, and the promoted/previous
agents.

`make submission-build` passed after promotion, producing
`submission_fixed.tar.gz` with `validation OK`. The promoted `main.py` was
synced to `kag-server` and its SHA-256 matched the local file.

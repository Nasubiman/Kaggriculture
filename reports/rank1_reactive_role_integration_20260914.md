# Rank 1: difficult-turn rule inference and integration (2026-09-14)

## Inferred policy structure

The aligned 255-game corpus does not support a greedy local-task policy.

- Across 1,218,992 actor-turns with at least one immediately available local task,
  rank 1 executed one immediately in 63.6% and moved/passed in 31.7%.
- WATER-only states led to WATER 80.6% of the time.
- HARVEST+WATER led to WATER 82.7% and HARVEST 10.5%.
- HARVEST+WATER+FERTILIZE split mainly into FERTILIZE 49.3% and WATER 39.2%.
- COLLECT-only led to COLLECT_FERTILIZER 84.0%.
- COLLECT+FEED+CARE led to FEED 80.7%.
- CARE-only and FERTILIZE-only were often deferred (immediate execution 20.0% and
  17.5%).

The most plausible model is therefore:

1. fixed or slowly changing worker roles;
2. a patrol/target route per role;
3. local task priority inside that route;
4. global economic gates that reassign roles or change herd/crop targets.

Actors 0--4 are livestock/mixed specialists, actor 5 is a transition worker, and
actors 6--10 are crop specialists. FEED is concentrated in early even hours,
CARE in early odd hours, harvesting around mid-day, and watering late in the day.

Detailed counts are in `reports/rank1_reactive_rules_20260914.md`.

## Integration

Directly overwriting a no-op with the locally dominant action was rejected. It
occasionally helped the results5-like opponent but caused very large regressions
against attack-style opponents, because a one-turn edit displaced the remaining
route.

Instead, `training/rank1_knn_runtime.py` now appends role-aware features for each
of 16 actors:

- categorical type of the tile under the actor;
- eight availability flags: WATER, HARVEST, FERTILIZE, FEED, CARE,
  COLLECT_FERTILIZER, PLANT, and near-shed work.

`training/rank1_chassis_runtime.py` uses these features when selecting a complete
rank-1 trajectory. Thus the inferred rule changes trajectory selection rather
than mutating an isolated action.

## Held-out opponent result

All numbers below are 20 seeds, both seats (40 games per opponent), using the
same 255 replay library. `role25_v2` uses a deliberately weak role/task weight.

| Opponent | Baseline wins | role25 wins | Baseline margin | role25 margin |
|---|---:|---:|---:|---:|
| attack_roundtrip_first25 | 23/40 | 23/40 | -2,598.4 | -2,015.6 |
| attack_roundtrip_q90 | 21/40 | 23/40 | -3,196.2 | -2,971.6 |
| incumbent_v37_opening | 21/40 | 21/40 | -2,656.5 | -2,520.7 |
| results5_20260913 | 21/40 | 21/40 | -3,436.4 | -4,483.8 |

The role-aware candidate gains two wins and improves three opponent margins, but
loses 1,047.4 mean margin against results5. Its summed four-opponent margin is
about 104 points worse (about 26 points worse on average), so it is retained as an experiment and is
not promoted to `main.py`.

Artifacts:

- candidate: `candidates/rank1_knn_255_role25_v2/`
- fair baseline: `reports/rank1_knn_255_pos4_strong20.json`
- candidate result: `reports/rank1_knn_255_role25_v2_strong20.json`
- isolated role result: `reports/rank1_knn_255_roleonly_v3_strong20.json`
- isolated task result: `reports/rank1_knn_255_taskonly_v3_strong20.json`

## Next design implication

Local priority is not sufficient. The next useful model should infer the
high-level target assignment itself: which actor owns which region, when a role
is reassigned, and what market/shop condition changes the desired herd/crop
mix. Those gates can then drive the existing route planners without switching
policy families mid-game.

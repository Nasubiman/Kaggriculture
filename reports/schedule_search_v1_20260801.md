# Daily schedule search v1 (2026-08-01)

## Outcome

The new search space and promotion pipeline are operational.  The first server
run did not pass the held-out gate, so `main.py` was not changed.

Run: `server-results/schedule_v1_20260801`

## New representation

The reactive low-level policy is retained, while a schedule genome controls:

- eight phase boundaries across the 30 days;
- intended herd size in every phase;
- hand cap in every phase;
- permanent animal-space allocation by quadrant;
- land count and each land-purchase day;
- last animal-purchase day;
- liquidation horizon;
- realization day and harvest priority.

The incumbent schedule reproduced the current `main.py` exactly over 24 parity
conditions.  A promoted standalone incumbent also reproduced it exactly.

## First search

League: `0801_ev4`, `0801_ev5`, `0801_v2`, `0801_ev6`.

- stage 0: 24 schedules, 3 seeds, both seats
- stage 1: top 12, 8 fresh seeds
- stage 2: 24 offspring, 12 fresh seeds
- final: top 3, 40 fresh seeds

The main surviving idea was the ev6-derived realization block:

- realization begins on day 22 instead of day 30;
- harvest priority changes from 2 to 1.

It was +178.3 on stage 2, but -186.7 on final held-out seeds.  Its final
per-opponent reward deltas were +24.6, -294.5, -168.1, and -308.7, so it was
correctly rejected.

## Commands

```sh
make schedule-search
make schedule-status
make schedule-candidate
make schedule-use
```

`schedule-use` refuses to modify `main.py` unless `decision.json` says the
held-out acceptance gate passed.

## Next expansion

The first version schedules economic targets but still delegates coordinates
and routing to the existing reactive planner.  The remaining gap to ev6 likely
requires scheduled spatial reservations and route templates, not just more
scalar values.

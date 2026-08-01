# Spatial trajectory search v1 (2026-08-02)

## Outcome

Run: `server-results/trajectory_20260802_014157`

The first spatial/action-order search passed its held-out gate.  The accepted
candidate was generated as `candidate_main.py`, backed up, promoted to
`main.py`, and packaged as `submission_fixed.tar.gz`.

Final paired evaluation used 100 untouched seeds, both seats, and four strong
opponents (`0801_ev4`, `0801_ev5`, `0801_v2`, `0801_ev6`):

- mean reward delta versus the incumbent: **+716.2**
- 95% lower bound: **+93.3**
- worst opponent mean delta: **+194.3**
- errors: **0**

Per-opponent reward deltas were +1,350.2 (ev4), +497.0 (ev5), +823.4
(v2), and +194.3 (ev6).  This is an incumbent improvement, not a solution to
the ev6 matchup: the held-out win rate against ev6 is still only 12.5%.

## What survived

The selected genome is much simpler than the ev6-inspired search space:

- retain the incumbent animal layout and crop layout;
- retain all incumbent service-priority blocks and travel costs;
- on days 4--9 only, use a row-wise snake sweep to break ties between jobs in
  the same safety priority tier;
- retain baseline ordering during every other part of the season.

The snake sweep alternates left-to-right and right-to-left on adjacent rows.
It changes target ordering without weakening critical feed or water jobs.  The
likely gain is less worker scattering and less duplicate cross-board travel
during the early expansion window.

The ev6 central-band layout and full ev6-style service program did not survive
the league gate.  The useful lesson from ev6 in this run was action ordering,
not literal geometry or herd size.

## Search space

`training/trajectory_genome.py` represents:

- explicit livestock layout families;
- crop fill paths;
- five swappable seasonal service blocks;
- five seasonal spatial sweep modes;
- phase-specific travel cost;
- phase boundaries and horizontal/vertical mirroring.

The compiler keeps the incumbent legality checks, crisis recovery, inventory
logic, and market policy.  Critical feed and water priorities cannot be
lowered by the genome.

On later runs, the search reads `_FROZEN_TRAJECTORY` from `main.py` and uses it
as the incumbent.  It therefore continues from this promoted row-snake policy
rather than silently reverting to the pre-trajectory engine.

`training/search_trajectory.py` uses paired incumbent deltas at identical
seed, opponent, and seat, followed by a completely untouched final seed set.
Acceptance requires a positive 95% lower bound, zero errors, and non-negative
mean delta against every opponent.

## Validation

The standalone candidate passed the Kaggle raw-file loader and full standard
runner in both seats against `random`:

- loader selected `kaggle_agent`;
- rewards: 151,951 and 155,308;
- both episodes completed with `DONE`;
- the tar archive contained one root-level `main.py`.

A separate standard-runner screen on five seeds in both seats had zero errors.
Relative to the incumbent, candidate mean reward increased by about +5,821
against ev4 and +13,991 against ev6.  These small-sample values are supporting
parity evidence; the 100-seed paired fast-runner gate remains the main result.

## Commands

```sh
make trajectory-search
make trajectory-status
make trajectory-candidate
make trajectory-use       # only succeeds when decision.json accepted=true
```

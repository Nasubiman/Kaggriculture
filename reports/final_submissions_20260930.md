# Final submissions (2026-09-30)

The two submissions that count for the final leaderboard:

| Submission | File | Agent | Notes |
|---|---|---|---|
| 56720443 | `submission_slot2/main.py` | ahd27s2 (`candidates/rs/ahd27s2.py`) | submitted 22:40 UTC, validation episode 115997884 completed |
| 56707260 | `submission_slot1/main.py` | d23a (`candidates/d23/d23a.py`) | submitted 12:24 UTC, 1974 at 22:40 UTC |

Both are the public results31 route-replay chassis (`candidates/results31/main.py`)
with constant changes and small wrapper layers appended at the end of the file.
Kaggle calls the file's last callable, so every wrapper captures the previous last
callable and the file must end with the outermost agent function.

## Lineage

Each step was kept only if it improved the mirror against results31 and did not
lose on recorded-opponent tapes.

| Agent | File | Change | Submission |
|---|---|---|---|
| sr24 | `candidates/results31_sr24.py` | `_SR_MARGIN = 24` | 56676118 |
| h12 | `candidates/r31srh/sr24_h12.py` | `_SR_HOURS = range(12, 24)`: sell wool mid-day instead of night dumps | 56690812 |
| ch95 | `candidates/ch95tom/ch95.py` | `_CH_SHED = 95` | 56692602 |
| cx8000 | `candidates/ch95tom/cx8000.py` | `_CXTB_MIN_REVENUE = 8000` (commit to tomatoes earlier) | |
| sh24 / sh24snk5 | `candidates/or2/` | `_OR2_SLOT_H = 24`, `_OR2_SN_K = 5` (pull tape sells forward, sell now) | |
| sh24_bfFW | `candidates/bf/sh24_bfFW.py` | buy-first: BUY_PRODUCT fertilizer/wheat before other non-SELL orders | 56694134 |
| sh48 / sh48snk5 | `candidates/s3/` | `_OR2_SLOT_H = 48` | |
| sncar | `candidates/car2/sncar.py` | carrots added to `_OR2_SN_ITEMS` | |
| d23a | `candidates/d23/d23a.py` | step 575: drop the fertilizer buy, cap the wheat buy at 5 (seen in 3 independent teams) | 56707260 |
| rgds_a | `candidates/st/rgds_a.py` | chassis `_SETTINGS`: `room_guard` and `dead_stock` on | |
| ahd27 | `candidates/hd/ahd27.py` | hour-23 harvest deferral (below) | |
| ahd27s2 | `candidates/rs/ahd27s2.py` | route swaps (below) | 56720443 |

### What the last three steps do

- **room_guard / dead_stock** (built into the chassis but disabled in results31):
  the end-of-day drop moves every worker's inventory into the shed and destroys
  anything beyond capacity 100. room_guard sells shed stock at hour 23 when that
  drop would overflow. dead_stock only acts on day 29: it sells the shed at once
  instead of on the tape's later steps, ahead of rivals running the same tape.
- **Harvest deferral** (`scripts/make_harvest_defer_variants.py`): most overflow
  comes from carried harvest while the shed is already empty, so room_guard cannot
  prevent it. At hour 23 of days <= 27, if the projected end-of-day total exceeds
  100, HARVEST commands on tiles whose yield can wait a day without loss
  (animals, strawberries/tomatoes with a production ahead and room under the
  held cap) become PASS. Wheat and carrots are never deferred (they decay).
- **Route swaps**: the router picks one of 41 route tapes from the first two
  shops, using tables shared by the whole results31 family. Tested against
  results31 on seeds that use each route, a few swaps win consistently:
  105/106/121/123 -> 107, 113 -> 116, 118 -> 101 (route 107 is route 105 with 7
  different steps on days 6-8; 121 is 105 plus a days 24-26 adjustment). Swapping
  route 9 (YARN_STORE pairs), 103, 110 or 112 to anything tested loses
  1.4k-12k per game. 104 -> 107 wins against results31 but flips sibling tapes to
  losses, so it is not included.

## Evidence

- Head-to-head (80 games, both seats): ahd27s2 vs d23a 62-4-14, vs sh24_bfFW
  64-0-16; d23a vs sh24_bfFW 69-0-11.
- Mirror vs results31 (160 games): d23a 156/4, +1009 per game; ahd27 +106 per
  game over d23a on the same seeds (+110 on 160 fresh seeds).
- Recorded-opponent tapes (`scripts/evaluate_vs_replay_tapes.py --force-money`;
  exact for our own recorded games): 142 recorded live games of our submissions
  (mostly sh24_bfFW), d23a 122 wins, ahd27s2 127; 1224 tapes from 614 replays of
  the newest submissions of about rank 200-500 teams, d23a 712 wins, ahd27s2 718
  (+68 per game).
- Decision time: about 2-4 ms mean, 0.4 s max per step (`scripts/timing.py`).

## Tried and rejected

- Dropping late fertilizer purchases (-600 to -3200 per game; fertilizer doubles
  strawberry yields) or the day-25/26 carrot seeds (-2700).
- Skipping feeds when a product is glutted: base production does not need feed,
  but sheep are fed two days in three, so any skip lets them escape and the lost
  fertilizer costs strawberries.
- Wheat washes (buy 40-75 wheat at step % 4 == 0 on days 10-15, sell the next
  step), common among higher-rated family teams: lost up to about 1100 per game
  against results31 in quick tests.
- Wider dead_stock (from day 27 or 28), adding wheat or fertilizer to the
  sell-now items (wheat: -3600 per game), clamp_sells, budget_guard, constant
  sweeps around d23a, carrot gate relaxations, the step-623 wheat cap.

## Tools

- `scripts/evaluate_agent_lc.py`: mirror / head-to-head over fixed seeds, both
  seats, loading the last callable.
- `scripts/evaluate_vs_replay_tapes.py`: candidate against recorded opponent
  action tapes (`--force-money`, `--exclude-teams`).
- `scripts/classify_mirror_replays.py`: teacher-force results31 on replays to find
  family players and where they diverge.
- `scripts/collect_band_replays.py`: download replays for a leaderboard rank band
  (`--latest --min-date` for teams' newest submissions).
- `scripts/tape_trade_diff.py`, `scripts/diagnose_mirror_game.py`,
  `scripts/executed_trades.py`: per-item revenue differences.
- `scripts/make_*_variants.py`: generate constant, late-trim, feed, harvest
  deferral, strawberry-fertilize and wheat-wash variants of a base file.

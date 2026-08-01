# 0801_ev6 analysis (2026-08-01)

## Conclusion

`0801_ev6` is a genuinely new opponent: a fixed 720-action trace distilled
from public episode `89256171`.  No tested policy change cleared the existing
multi-opponent acceptance gate, so `main.py` was deliberately left unchanged.
The opponent and coherent multi-gene hypotheses were added to the normal
paired-search workflow.

## Current main against ev6

100 seeds, both seats (200 games):

- wins: 19/200 (9.5%)
- mean margin: -11,732.8
- mean reward: 116,111.4
- errors: 0

Source: `reports/before_ev6_gate_100.json`.

This is not merely a counter matchup.  When ev6 itself was evaluated for 40
seeds in both seats, it beat ev4 80/80, ev5 80/80, and v2 79/80, with mean
rewards of 131,908--135,749.  Source: `reports/ev6_vs_league_40.json`.

## Strategy extracted from the fixed trace

- day 1: 3 cows, 1 sheep, 4 hands, 6 melon seeds
- day 7: +2 cows
- day 9: +3 sheep and first extra land
- day 11: +4 cows
- day 12: second extra land
- day 17: +3 sheep
- intended final mix: 9 cows and 7 sheep
- fertilizer becomes material from day 13
- harvesting becomes dominant from roughly day 22
- day 30 contains harvesting and terminal sales

The important point is that these choices are coupled.  Copying only the herd
size or land dates does not reproduce the trace's routing and crop layout.

## Paired structural tests

The most useful structural candidate increased capacity and target herd from
13 to 16.  On a separate 16-seed stage (32 games per opponent), its reward
delta versus the incumbent was:

| Opponent | Mean reward delta |
|---|---:|
| 0801_ev4 | -3,559.6 |
| 0801_ev5 | -3,186.4 |
| 0801_v2 | +318.8 |
| 0801_ev6 | +5,652.8 |
| Overall | -193.6 |

It is a useful ev6 counter, but fails the worst-opponent gate and is not a
general upgrade.  Delaying land to days 9/12 scored -7,909.8 overall, and the
full trace-like three-stage profile scored -15,084.3 overall.

Two follow-up gates were also rejected:

1. Opponent-conditioned 16-herd expansion improved ev6 win rate from 9.5% to
   12.0%, but reduced v2 from 82.5% to 78-79% and lowered mean reward.
2. A general fourth herd gate at day 17 was already clearly negative on three
   probe seeds for every opponent (-3,501 to -8,103 mean reward delta).

## Changes retained

- `0801_ev6` is now in the default paired-search league.
- Stage 0 includes coherent multi-gene structural profiles in addition to
  single-coordinate mutations.
- Structural profiles are explicitly retained through stages 1 and 2 instead
  of being accidentally discarded by the single-gene selector.
- Candidate and opponent agents are cached per worker, avoiding repeated
  imports of the 132 KB fixed-trace module for every episode.

Rejected experiments were reverted; the submitted policy remains the previous
validated incumbent.

The next policy-level improvement should therefore model an entire daily
schedule (layout, routing, purchases, and terminal realization together), not
add more independent scalar gates to the current reactive policy.

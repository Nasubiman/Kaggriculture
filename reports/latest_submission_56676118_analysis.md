# Submission 56676118: public-game analysis and shop-pair improvement

Collected 2026-09-30. The Kaggle CLI reports submission `56676118` as the latest
completed submission, described as `results31 + _SR_MARGIN=24` (public score
1790.5). Its local byte-identical copy is `submission_slot1/main.py`, not the
repository-root `main.py`. Before this analysis, root `main.py` was identical
to `candidates/partial/sel_t10.py` (submission `56598193`, public score 1890.7).

## Actual public games

All 31 public replays for submission `56676118` were downloaded to
`replays/latest_submission_56676118/`. The submitted agent finished every
game: 22 wins, 7 losses, 2 ties. Twelve games had final absolute margin at most
1,000; 19 had margin at most 3,000. Thus many wins and losses are narrow
market-timing races between similar strategies.

Six of seven losses were within 3,000. The exceptional loss was episode
`115277820` against elmo, on `PET_CAFE → YARN_STORE`: 42,137 to 80,487.
Our agent led by 4,616 at step 287, but trailed by 12,718 at step 431 and
38,350 at the end. Elmo bought 5 cows, 14 sheep, and 8 geese and sold
473 wheat, 410 carrots, and 262 eggs; our agent bought 6 cows and 11 sheep
and sold 306 wheat, 229 carrots, and no eggs. This is a production-system
gap, not merely a last-turn sales-order error. One such game is not enough
evidence to force a wholesale herd-policy change.

The compact per-episode data are in `reports/latest_submission_56676118_analysis.json`.
The server-ready action tapes are in
`replays/latest_submission_56676118/opponent_tapes.json.gz` (827 KiB), so
the 33 MB-per-game replay JSON files need not be copied to the server.

## Candidate comparison

Replaying the actual opponents' actions on the recorded seeds reproduced the
latest submission's 31 results exactly. `results31` base won 21/31,
`_SR_MARGIN=14` won 21/31, submitted `_SR_MARGIN=24` won 22/31, and the
previous root `main.py` (`sel_t10`) won 23/31. On four established opponents
and 40 independent seeds (both seats, 320 games), submitted SR24 won 274/320
and `sel_t10` won 302/320. Therefore the overall `results31` replacement
was not justified as a new root-main baseline.

The only shop pair in that 320-game comparison where SR24 gained wins over
`sel_t10` was `SMOOTHIE_SHOP → BAKERY` (24/24 versus 22/24). An experimental
single-pair switch increased the total to 304/320. On 21 newly selected,
independent seeds containing that pair, versus `results28` and Harvest Ledger
in both seats, it won 81/84 versus `sel_t10`'s 78/84: three losses became
wins and no wins were lost. A separate untargeted 400-game holdout had zero
instances of this pair, so both versions scored 342/400; it was not evidence
about the switch. The switch also retained 23/31 on the latest real-opponent
tapes and, on a target-pair seed, exactly matched the official standard
simulator's reward and status in both seats.

The accepted change is limited to the `SMOOTHIE_SHOP → BAKERY` entry in
root `main.py`'s day-six shop-pair selector. A complete SR24 agent is embedded
as one additional secondary; the original policy remains the fallback and
all other pair mappings remain unchanged. This is a small expected overall
win-rate gain because the pair is uncommon. It adds runtime before day six;
that cost should be monitored in any live submission. The simple scalar
alternatives (`_SR_MARGIN` 24 or 40 inside the existing secondary) failed to
improve the 84-game targeted holdout and were not adopted.

`main.py` was updated locally but **not submitted to Kaggle**. The exact
tested single-file candidate is `candidates/shop_override_smoothie_bakery_sr24.py`.

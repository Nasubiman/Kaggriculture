# Rank-1 imitation progress — 2026-09-14

## Outcome

The first state-conditioned trajectory policy is competitive with the current
`results5_20260913` model, but is not yet safe to promote.  The best 20-seed,
both-seat result is 21/40 wins (52.5%) with mean margin -2,321.1.  The negative
mean comes from a small number of large losses, so `main.py` remains unchanged.

## Data correction and expansion

- Kaggle replay alignment is `observation[t] -> action[t+1]`.
- Unaligned datasets are deprecated because they leak the next state.
- Rank-1 submission 56156662 grew from 235 to 255 public episodes.
- Latest aligned compact dataset: 183,345 examples.
- Late-game action diversity is genuine: macro actions have 255 variants at
  many steps, so one fixed tape cannot represent the policy.

## Experiments

| Policy | Main observation | Result |
|---|---|---|
| Exact fixed public tape | No adaptation | Best search: 15.5% league win rate |
| Behavior cloning | Distribution shift | Actor commands disappear from the demonstrated trajectory; unusable |
| Per-step nearest trajectory | Uses own/opponent state | About 94k mean reward in the initial league smoke test |
| Nearest trajectory + route chassis | Adds weed/sell/budget/storage repair | 35–45% versus most league members |
| Remove opponent from matching distance | Avoids opponent correlation as a route selector | 50% versus results5 over 40 games |
| Also emphasize worker positions/carried goods | Preserves spatial route phase | 52.5% versus results5 over 40 games |

Best evaluated 235-game candidate: `candidates/rank1_knn_own_pos4`.
Latest 255-game equivalent: `candidates/rank1_knn_255_pos4`.

## Strong-opponent result (20 seeds, both seats)

| Opponent | Wins | Win rate | Mean margin | Mean reward |
|---|---:|---:|---:|---:|
| attack_roundtrip_first25 | 22/40 | 55.0% | -3,878.9 | 94,754.9 |
| attack_roundtrip_q90 | 22/40 | 55.0% | -4,038.1 | 95,408.9 |
| incumbent_v37_opening | 19/40 | 47.5% | -4,273.5 | 92,491.0 |
| results5_20260913 | 21/40 | 52.5% | -2,321.1 | 98,719.3 |

## Rejected ideas

- Per-actor legal-command replacement destroys coordinated work order.
- Top-k action voting averages incompatible trajectory phases.
- Favoring high-reward public episodes learns favorable market seeds rather
  than stronger decisions and sharply reduces reward.
- Fixed 2/4/6/24-step switching and route hysteresis did not remove the loss
  tail; immediate nearest-neighbor switching remains stronger.

## Next technical target

Keep the complete nearest trajectory action, but learn when its route is unsafe.
The next gate should use own-state distance and projected resource feasibility,
with the incumbent evaluated in parallel as a recovery policy.  Promotion
requires positive mean margin and no strong-opponent regression on held-out
seeds, not win rate alone.

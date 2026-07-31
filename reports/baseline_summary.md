# Baseline evaluation

The history-informed `main.py` baseline was evaluated against the built-in
`starter` and `random` agents using seeds 101, 202, and 303, from both player
positions.

| Metric | Result |
|---|---:|
| Games | 12 |
| Completed normally | 12 / 12 |
| Wins | 12 / 12 |
| Mean final reward | 23,346 |
| Reward standard deviation | 4,696 |
| Mean winning margin | +21,612 |

This is a functional baseline rather than a leaderboard-level strategy. The
sampled top-five public histories averaged roughly 50k–98k reward, so the next
optimization target is workforce routing and animal economics.

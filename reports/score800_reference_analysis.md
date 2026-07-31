# Score-800 reference: Harvest Pulse

Source: user-provided `Harvest Pulse | Adaptive Landrush Baseline`.

## Core design

- Fixed 25-tile core: 13 melon, 4 carrot, 4 wheat, 2 tomato, 2 strawberry.
- Seven farm hands hired during hours 0–5.
- Northeast land purchased on day 11.
- Fifteen wheat plots added after expansion.
- Melons harvested early at age 10 once six units are available.
- Melon sales are clipped to two units per turn until final liquidation.
- Every unit receives a distinct reserved task from a deterministic board plan.
- Core tasks take precedence over northeast expansion tasks.

## Direct comparison with the current baseline

The reference agent was loaded without modification and played against the
current `main.py` on seeds 101, 202, and 303, from both player positions.

| Metric | Harvest Pulse | Current baseline |
|---|---:|---:|
| Wins | 6 / 6 | 0 / 6 |
| Mean reward | 37,800.5 | 11,168.8 |

The largest reusable advantages are its fixed crop-to-tile plan, exact seed
demand calculation, conservative seven-worker cap, core-first task scheduling,
and gradual melon liquidation. These are better candidates for the next version
than simply increasing worker count or land area.

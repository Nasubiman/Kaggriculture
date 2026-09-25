#!/usr/bin/env python3
"""Print expansion-relevant decisions from a candidate's fast episode."""

from __future__ import annotations

import argparse
from pathlib import Path

from kaggle_environments.agent import get_last_callable
from production_fast_kaggriculture import run_fast_episode


def load(path: Path):
    return get_last_callable(path.read_text(encoding="utf-8"), path=str(path))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, default=Path("main.py"))
    parser.add_argument("--opponent", type=Path, default=Path("test/results29_20260924/main.py"))
    parser.add_argument("--seed", type=int, default=13095065)
    parser.add_argument("--seat", type=int, choices=(0, 1), default=0)
    args = parser.parse_args()
    candidate = load(args.candidate.resolve())
    opponent = load(args.opponent.resolve())
    previous_quadrants = 1

    def observed(observation):
        nonlocal previous_quadrants
        action = candidate(observation)
        step = int(observation["step"])
        farm = observation["farms"][args.seat]
        quadrants = len(farm["unlocked_quadrants"])
        market = action.get("market") or []
        land = any(order and order[0] == "BUY_LAND" for order in market)
        if (quadrants != previous_quadrants or land or step in
                (145, 146, 147, 196, 197, 198, 199, 219, 220, 246, 247, 248, 249, 250, 253, 254, 265, 288)):
            print({"step": step, "quadrants": quadrants,
                   "cash": int(farm["money"]), "land": land,
                   "market": market})
        previous_quadrants = quadrants
        return action

    agents = [observed, opponent] if args.seat == 0 else [opponent, observed]
    result = run_fast_episode(agents, seed=args.seed)
    print({"final_rewards": [float(item.reward or 0) for item in result]})


if __name__ == "__main__":
    main()

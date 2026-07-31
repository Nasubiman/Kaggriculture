#!/usr/bin/env python3
"""Print day-level state and action counts for a local cow-agent game."""

from __future__ import annotations

import argparse
import importlib.util
import json
from collections import Counter
from pathlib import Path

from kaggle_environments import make


ROOT = Path(__file__).resolve().parents[1]


def load_agent(path: Path):
    spec = importlib.util.spec_from_file_location(
        f"diagnostic_{path.stem}", path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.agent


def cow_tiles(farm: dict) -> list[dict]:
    return [
        tile
        for row in farm["tiles"]
        for tile in row
        if isinstance(tile, dict) and tile.get("animal") == "COW"
    ]


def tile_mix(farm: dict) -> Counter[str]:
    mix: Counter[str] = Counter()
    for row in farm["tiles"]:
        for tile in row:
            if not isinstance(tile, dict):
                continue
            if tile.get("animal"):
                mix[str(tile["animal"])] += 1
            elif tile.get("kind") == "PLANT":
                mix[str(tile.get("crop"))] += 1
            elif tile.get("kind"):
                mix[str(tile["kind"])] += 1
    return mix


def operation_counts(states: list, seat: int) -> Counter[str]:
    counts: Counter[str] = Counter()
    for state in states:
        player_state = state[seat]
        action = (
            player_state.get("action")
            if isinstance(player_state, dict)
            else player_state.action
        ) or {}
        for field_action in [
            action.get("farmer"),
            *(action.get("hands") or []),
        ]:
            if field_action:
                operation = str(field_action[0])
                counts[operation] += 1
        for market_action in action.get("market") or []:
            if market_action:
                operation = str(market_action[0])
                if len(market_action) > 1:
                    operation += f"_{market_action[1]}"
                counts[operation] += 1
    return counts


def market_quantities(states: list, seat: int) -> Counter[str]:
    quantities: Counter[str] = Counter()
    for state in states:
        player_state = state[seat]
        action = (
            player_state.get("action")
            if isinstance(player_state, dict)
            else player_state.action
        ) or {}
        for market_action in action.get("market") or []:
            if not market_action:
                continue
            label = str(market_action[0])
            if len(market_action) > 1:
                label += f"_{market_action[1]}"
            amount = (
                int(market_action[-1])
                if isinstance(market_action[-1], (int, float))
                else 1
            )
            quantities[label] += amount
    return quantities


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--candidate",
        type=Path,
        default=ROOT / "main.py",
    )
    parser.add_argument(
        "--reference",
        type=Path,
        default=ROOT / "agents" / "pulse_breaker_v2.py",
    )
    parser.add_argument("--seed", type=int, default=101)
    parser.add_argument("--seat", type=int, choices=(0, 1), default=0)
    parser.add_argument(
        "--replay",
        type=Path,
        help="Analyze a saved replay instead of running a local game.",
    )
    parser.add_argument(
        "--verbose-market",
        action="store_true",
        help="Print requested market quantities for every day.",
    )
    args = parser.parse_args()

    if args.replay:
        replay = json.loads(
            args.replay.resolve().read_text(encoding="utf-8")
        )
        steps = replay["steps"]
        rewards = replay["rewards"]
        statuses = replay["statuses"]
    else:
        candidate = load_agent(args.candidate.resolve())
        reference = load_agent(args.reference.resolve())
        agents = (
            [candidate, reference]
            if args.seat == 0
            else [reference, candidate]
        )
        env = make(
            "kaggriculture",
            configuration={"episodeSteps": 720, "seed": args.seed},
            debug=True,
        )
        env.run(agents)
        steps = env.steps
        rewards = [
            state.reward for state in env.steps[-1]
        ]
        statuses = [
            state.status for state in env.steps[-1]
        ]

    print(
        "day money cows shedCow wheat milk fert hands "
        "unfed2 feed care collect harvest place"
    )
    for day in range(30):
        start = day * 24
        state = steps[start][args.seat]
        observation = (
            state["observation"]
            if isinstance(state, dict)
            else state.observation
        )
        farm = observation["farms"][args.seat]
        private = observation["private"]
        shed = private.get("shed", {}) or {}
        cows = cow_tiles(farm)
        counts = operation_counts(
            steps[start : min(start + 24, len(steps))],
            args.seat,
        )
        market = market_quantities(
            steps[start : min(start + 24, len(steps))],
            args.seat,
        )
        max_hands = max(
            len(
                (
                    step[args.seat]["observation"]
                    if isinstance(step[args.seat], dict)
                    else step[args.seat].observation
                )["farms"][args.seat].get("hands", [])
            )
            for step in steps[start : min(start + 24, len(steps))]
        )
        print(
            day,
            int(farm.get("money", 0)),
            len(cows),
            int(shed.get("COW", 0)),
            int(shed.get("WHEAT", 0)),
            int(shed.get("MILK", 0)),
            int(shed.get("FERTILIZER", 0)),
            max_hands,
            sum(
                int(cow.get("consecutive_unfed", 0)) >= 1
                for cow in cows
            ),
            counts["FEED"],
            counts["CARE"],
            counts["COLLECT_FERTILIZER"],
            counts["HARVEST"],
            counts["PLACE"],
        )
        if args.verbose_market and market:
            mix = tile_mix(farm)
            print(
                "  tiles:",
                ", ".join(
                    f"{item}={amount}"
                    for item, amount in sorted(mix.items())
                ),
            )
            print(
                "  market:",
                ", ".join(
                    f"{operation}={amount}"
                    for operation, amount in sorted(market.items())
                ),
            )

    total = operation_counts(steps, args.seat)
    print(
        f"reward={rewards[args.seat]:.0f} "
        f"opponent={rewards[1 - args.seat]:.0f} "
        f"status={statuses[args.seat]}"
    )
    print("total operations:")
    for operation, count in total.most_common():
        print(f"  {operation}: {count}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Summarize daily economics and actions on selected head-to-head seeds."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from kaggle_environments.agent import get_last_callable
from production_fast_kaggriculture import run_fast_episode


def load(path: Path):
    agent = get_last_callable(path.read_text(encoding="utf-8"), path=str(path))
    if not callable(agent):
        raise RuntimeError(f"no agent in {path}")
    return agent


def tile_counts(farm):
    crops = Counter()
    animals = Counter()
    for row in farm["tiles"]:
        for tile in row:
            if not isinstance(tile, dict):
                continue
            if tile.get("crop"):
                crops[tile["crop"]] += 1
            if tile.get("animal"):
                animals[tile["animal"]] += 1
    return dict(crops), dict(animals)


def farm_similarity(farms, player):
    own = farms[player]
    rival = farms[1 - player]
    if own["unlocked_quadrants"] != rival["unlocked_quadrants"]:
        return 0.0
    matches = total = 0
    for own_row, rival_row in zip(own["tiles"], rival["tiles"]):
        for own_tile, rival_tile in zip(own_row, rival_row):
            a = (own_tile.get("crop"), own_tile.get("animal")) if isinstance(own_tile, dict) else (None, None)
            b = (rival_tile.get("crop"), rival_tile.get("animal")) if isinstance(rival_tile, dict) else (None, None)
            if a != (None, None) or b != (None, None):
                total += 1
                matches += a == b
    return matches / total if total >= 8 else 0.0


def play(candidate, opponent, seed: int, seat: int):
    days = [{"seed": seed, "seat": seat, "day": day, "players": {}}
            for day in range(30)]
    counters = [[Counter() for _ in range(30)] for _ in range(2)]
    units = [[Counter() for _ in range(30)] for _ in range(2)]
    agents = [candidate, opponent] if seat == 0 else [opponent, candidate]

    def instrument(agent, player):
        def call(observation):
            step = int(observation["step"])
            day = min(step // 24, 29)
            if step % 24 == 0:
                farm = observation["farms"][player]
                crops, animals = tile_counts(farm)
                days[day]["players"][str(player)] = {
                    "money": float(farm["money"]),
                    "hands": len(farm["hands"]),
                    "crops": crops,
                    "animals": animals,
                    "similarity": farm_similarity(observation["farms"], player),
                    "shed": dict(observation["private"]["shed"]),
                    "seeds": dict(observation["private"]["seeds"]),
                }
            action = agent(observation)
            for order in action.get("market") or []:
                if not order:
                    continue
                name = order[0] + (":" + str(order[1]) if len(order) > 1 else "")
                counters[player][day][name] += int(order[2]) if len(order) > 2 else 1
            for command in [action.get("farmer") or ["PASS"], *(action.get("hands") or [])]:
                if command:
                    units[player][day][command[0]] += 1
            return action
        return call

    final = run_fast_episode([instrument(agent, player) for player, agent in enumerate(agents)], seed=seed)
    for day, row in enumerate(days):
        for player in (0, 1):
            row["players"].setdefault(str(player), {})["market_orders"] = dict(counters[player][day])
            row["players"][str(player)]["unit_actions"] = dict(units[player][day])
    rewards = [float(entry.reward) for entry in final]
    return {"seed": seed, "seat": seat, "margin": rewards[seat] - rewards[1-seat],
            "rewards": rewards, "days": days}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, default=Path("main.py"))
    parser.add_argument("--opponent", type=Path, required=True)
    parser.add_argument("--seeds", type=int, nargs="+", required=True)
    parser.add_argument("--seat", type=int, choices=(0, 1), default=0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    candidate = load(args.candidate)
    opponent = load(args.opponent)
    games = [play(candidate, opponent, seed, args.seat) for seed in args.seeds]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"games": games}, indent=2) + "\n")
    for game in games:
        print(f"seed={game['seed']} margin={game['margin']:+.0f}", flush=True)
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()

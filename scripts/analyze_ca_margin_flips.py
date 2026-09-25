#!/usr/bin/env python3
"""Inspect the first action divergence in paired strategy win flips."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from kaggle_environments.agent import get_last_callable
from production_fast_kaggriculture import run_fast_episode


class FirstDifference(Exception):
    def __init__(self, row):
        super().__init__("candidate action diverged")
        self.row = row


def load_raw_agent(path: Path):
    agent = get_last_callable(path.read_text(encoding="utf-8"), path=str(path))
    if not callable(agent):
        raise RuntimeError(f"{path} does not define a callable entry point")
    return agent


def counts(farm):
    crops = {}
    animals = {}
    for row in farm["tiles"]:
        for tile in row:
            if not isinstance(tile, dict):
                continue
            crop = tile.get("crop")
            animal = tile.get("animal")
            if crop:
                crops[crop] = crops.get(crop, 0) + 1
            if animal:
                animals[animal] = animals.get(animal, 0) + 1
    return crops, animals


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paired", type=Path, required=True)
    parser.add_argument("--agent", type=Path, default=Path("main.py"))
    parser.add_argument("--models-dir", type=Path, default=Path("test"))
    parser.add_argument("--variant", default="ca20")
    parser.add_argument("--down-only", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    paired = json.loads(args.paired.read_text())
    by_game = {}
    for row in paired["games"]:
        by_game.setdefault((row["opponent"], row["seed"], row["seat"]), {})[row["variant"]] = row
    flips = []
    for (opponent, seed, seat), variants in by_game.items():
        base_row = variants.get("baseline")
        new_row = variants.get(args.variant)
        if (base_row and new_row and base_row["win"] != new_row["win"]
                and (not args.down_only or base_row["win"])):
            flips.append((opponent, seed, seat, base_row, new_row))

    base = load_raw_agent(args.agent)
    alternative = load_raw_agent(args.agent)
    if args.variant == "ca20":
        alternative.__globals__["_CA_MARGIN"] = -20.0
    elif args.variant == "no_v12_frontload":
        alternative.__globals__["_v12_frontload"] = lambda _observation, action: action
    elif args.variant == "frontload_investments_only":
        original = alternative.__globals__["_v12_frontload"]
        def selective_frontload(observation, action):
            orders = action.get("market") or []
            if any(order and order[0] in ("BUY_LAND", "BUY_ANIMAL") for order in orders):
                return original(observation, action)
            return action
        alternative.__globals__["_v12_frontload"] = selective_frontload
    else:
        parser.error(f"unsupported variant: {args.variant}")
    opponents = {}
    results = []
    for opponent, seed, seat, base_row, new_row in flips:
        if opponent not in opponents:
            path = args.models_dir / opponent / "main.py"
            opponents[opponent] = load_raw_agent(path)

        def probe(observation):
            original_action = base(observation)
            altered_action = alternative(observation)
            if original_action == altered_action:
                return original_action
            our_farm = observation["farms"][seat]
            their_farm = observation["farms"][1 - seat]
            own_crops, own_animals = counts(our_farm)
            their_crops, their_animals = counts(their_farm)
            market = observation["market"]
            raise FirstDifference({
                "opponent": opponent,
                "seed": seed,
                "seat": seat,
                "flip": "up" if new_row["win"] else "down",
                "base_margin": base_row["margin"],
                "new_margin": new_row["margin"],
                "step": int(observation["step"]),
                "day": int(observation["step"]) // 24,
                "shops": list(observation["town"]["unlocked_shops"]),
                "prices": {item: float(market["prices"][item]) for item in ("WHEAT", "CARROT", "TOMATO")},
                "market_inventory": {item: int(market["inventory"][item]) for item in ("WHEAT", "CARROT", "TOMATO")},
                "own_crops": own_crops,
                "their_crops": their_crops,
                "own_animals": own_animals,
                "their_animals": their_animals,
                "own_money": float(our_farm["money"]),
                "their_money": float(their_farm["money"]),
                "original_action": original_action,
                "altered_action": altered_action,
            })

        lineup = [probe, opponents[opponent]] if seat == 0 else [opponents[opponent], probe]
        try:
            run_fast_episode(lineup, seed=seed)
        except FirstDifference as difference:
            results.append(difference.row)
        else:
            results.append({"opponent": opponent, "seed": seed, "seat": seat, "error": "no action divergence"})
        print(f"analyzed {len(results)}/{len(flips)}", flush=True)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2) + "\n")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()

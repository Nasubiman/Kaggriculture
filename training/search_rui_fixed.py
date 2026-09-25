#!/usr/bin/env python3
"""Evaluate fixed profiles reconstructed from RuiKimura4 public replays."""

from __future__ import annotations

import argparse
import importlib.util
import json
import multiprocessing as mp
import os
from pathlib import Path
from statistics import mean
from typing import Any

from production_fast_kaggriculture import run_fast_episode


ROOT = Path(__file__).resolve().parents[1]

DAY0_SCRIPT = json.loads(r'''{"0":{"farmer":["PASS"],"hands":[],"market":[["HIRE"],["HIRE"],["HIRE"],["HIRE"],["HIRE"],["HIRE"],["BUY_SEED","MELON",16],["BUY_SEED","CARROT",6],["BUY_ANIMAL","COW",2]]},"1":{"farmer":["BUILD_PASTURE"],"hands":[["WEST"],["NORTH"],["PASS"],["NORTH"],["WEST"],["NORTH"]],"market":[["BUY_PRODUCT","WHEAT",5]]},"2":{"farmer":["PICKUP","COW",1],"hands":[["NORTH"],["WEST"],["PASS"],["BUILD_PASTURE"],["NORTH"],["WEST"]],"market":[]},"3":{"farmer":["PLACE","COW"],"hands":[["SOUTH"],["PLANT","MELON"],["PASS"],["NORTH"],["WEST"],["WEST"]],"market":[]},"4":{"farmer":["PICKUP","WHEAT",3],"hands":[["PICKUP","COW",1],["WATER"],["PASS"],["PLANT","MELON"],["PLANT","MELON"],["PLANT","MELON"]],"market":[]},"5":{"farmer":["FEED"],"hands":[["NORTH"],["EAST"],["PASS"],["WATER"],["WATER"],["WATER"]],"market":[]},"6":{"farmer":["CARE"],"hands":[["PLACE","COW"],["WEST"],["PASS"],["NORTH"],["NORTH"],["NORTH"]],"market":[["BUY_PRODUCT","WHEAT",1]]},"7":{"farmer":["NORTH"],"hands":[["CARE"],["WEST"],["PASS"],["PLANT","MELON"],["PLANT","MELON"],["PLANT","MELON"]],"market":[]},"8":{"farmer":["FEED"],"hands":[["NORTH"],["WEST"],["PASS"],["WATER"],["WATER"],["WATER"]],"market":[]},"9":{"farmer":["WEST"],"hands":[["WEST"],["PLANT","MELON"],["PASS"],["NORTH"],["NORTH"],["NORTH"]],"market":[["BUY_PRODUCT","WHEAT",1]]},"10":{"farmer":["WEST"],"hands":[["WEST"],["WATER"],["PASS"],["PLANT","MELON"],["PLANT","MELON"],["PLANT","MELON"]],"market":[]},"11":{"farmer":["WEST"],"hands":[["WATER"],["WEST"],["PASS"],["WATER"],["WATER"],["NORTH"]],"market":[]},"12":{"farmer":["PLANT","MELON"],"hands":[["WEST"],["PLANT","MELON"],["PASS"],["WEST"],["WEST"],["PLANT","MELON"]],"market":[]},"13":{"farmer":["WATER"],"hands":[["PLANT","MELON"],["WATER"],["PASS"],["PLANT","MELON"],["WATER"],["WEST"]],"market":[]},"14":{"farmer":["WEST"],"hands":[["WATER"],["NORTH"],["PASS"],["WATER"],["NORTH"],["PLANT","CARROT"]],"market":[]},"15":{"farmer":["PLANT","CARROT"],"hands":[["WEST"],["NORTH"],["PASS"],["WEST"],["PLANT","CARROT"],["WATER"]],"market":[]},"16":{"farmer":["WATER"],"hands":[["PLANT","CARROT"],["NORTH"],["PASS"],["WATER"],["WEST"],["EAST"]],"market":[]},"17":{"farmer":["EAST"],"hands":[["WATER"],["PLANT","CARROT"],["PASS"],["SOUTH"],["PLANT","CARROT"],["SOUTH"]],"market":[]},"18":{"farmer":["EAST"],"hands":[["EAST"],["WATER"],["PASS"],["SOUTH"],["WATER"],["EAST"]],"market":[]},"19":{"farmer":["EAST"],"hands":[["EAST"],["EAST"],["PASS"],["EAST"],["SOUTH"],["SOUTH"]],"market":[]},"20":{"farmer":["EAST"],"hands":[["EAST"],["EAST"],["PASS"],["SOUTH"],["EAST"],["EAST"]],"market":[]},"21":{"farmer":["SOUTH"],"hands":[["SOUTH"],["SOUTH"],["PASS"],["EAST"],["SOUTH"],["SOUTH"]],"market":[]},"22":{"farmer":["PASS"],"hands":[["EAST"],["EAST"],["PASS"],["SOUTH"],["EAST"],["PASS"]],"market":[]},"23":{"farmer":["PASS"],"hands":[["SOUTH"],["SOUTH"],["PASS"],["PASS"],["SOUTH"],["PASS"]],"market":[]}}''')

OPENING_PLAN = {
    (1, 0): "CARROT", (2, 0): "CARROT", (3, 0): "MELON", (4, 0): "MELON",
    (0, 1): "CARROT", (1, 1): "CARROT", (2, 1): "MELON", (3, 1): "MELON",
    (4, 1): "MELON", (0, 2): "CARROT", (1, 2): "MELON", (2, 2): "MELON",
    (3, 2): "MELON", (4, 2): "MELON", (0, 3): "CARROT", (1, 3): "MELON",
    (2, 3): "MELON", (3, 3): "MELON", (0, 4): "MELON", (1, 4): "MELON",
    (2, 4): "MELON", (3, 4): "MELON",
}

RUI8_COWS = [
    (4, 4), (4, 3), (3, 2), (4, 2),
    (5, 3), (3, 4), (5, 4), (6, 4),
]
RUI8_SHEEP = [
    (4, 0), (5, 0), (5, 2), (6, 2),
    (2, 3), (7, 3), (1, 4), (7, 4),
]
RUI8_STRAWBERRY = [
    (3, 0), (6, 0), (2, 1), (3, 1), (4, 1),
    (5, 1), (6, 1), (7, 1), (1, 2), (2, 2),
    (7, 2), (8, 2), (1, 3), (3, 3), (6, 3),
    (8, 3), (0, 4), (2, 4), (8, 4), (9, 4),
]
RUI11_COWS = [
    (4, 4), (4, 3), (3, 2), (4, 2), (5, 2), (6, 2),
    (5, 3), (7, 3), (3, 4), (5, 4), (6, 4),
]
RUI11_SHEEP = [
    (2, 0), (4, 0), (5, 0), (3, 1),
    (2, 3), (9, 3), (1, 4), (7, 4),
]
RUI11_STRAWBERRY = [
    (3, 0), (6, 0), (2, 1), (4, 1), (5, 1),
    (6, 1), (7, 1), (1, 2), (2, 2), (7, 2),
    (8, 2), (0, 3), (1, 3), (3, 3), (6, 3),
    (8, 3), (0, 4), (2, 4), (8, 4), (9, 4),
]
RUI12_COWS = [
    (4, 4), (4, 3), (3, 2), (4, 2), (5, 2), (6, 2),
    (2, 3), (5, 3), (7, 3), (3, 4), (5, 4), (6, 4),
]
RUI12_SHEEP = [
    (6, 0), (2, 1), (7, 1), (1, 2),
    (8, 2), (1, 4), (7, 4), (8, 4),
]
RUI12_STRAWBERRY = [
    (3, 0), (4, 0), (5, 0), (3, 1), (4, 1), (5, 1),
    (6, 1), (2, 2), (7, 2), (1, 3), (3, 3), (6, 3),
    (8, 3), (0, 4), (2, 4), (9, 4),
]

VARIANTS = {
    "incumbent": None,
    "rui8_no_cash": (RUI8_COWS, RUI8_SHEEP, []),
    "rui8_no_cash_cowfirst": (RUI8_COWS, RUI8_SHEEP, []),
    "rui8_no_cash_cowfirst_h11": (RUI8_COWS, RUI8_SHEEP, []),
    "rui8_no_cash_cowfirst_h11_noreplant": (RUI8_COWS, RUI8_SHEEP, []),
    "rui7_s8_cowfirst": (RUI8_COWS[:7], RUI8_SHEEP, []),
    "rui8_s7_cowfirst": (RUI8_COWS, RUI8_SHEEP[:7], []),
    "rui7_s7_cowfirst": (RUI8_COWS[:7], RUI8_SHEEP[:7], []),
    "rui8_cash4_cowfirst": (RUI8_COWS, RUI8_SHEEP, RUI8_STRAWBERRY[:4]),
    "rui8_cash8_cowfirst": (RUI8_COWS, RUI8_SHEEP, RUI8_STRAWBERRY[:8]),
    "rui8_cash20": (RUI8_COWS, RUI8_SHEEP, RUI8_STRAWBERRY),
    "rui11_cash20": (RUI11_COWS, RUI11_SHEEP, RUI11_STRAWBERRY),
    "rui12_cash16": (RUI12_COWS, RUI12_SHEEP, RUI12_STRAWBERRY),
}


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def configure(module: Any, name: str):
    profile = VARIANTS[name]
    if profile is None:
        return module.agent
    cows, sheep, strawberries = profile
    module.COW_START_DAY = 10
    module.COW_TARGET = len(cows)
    module.SHEEP_TARGET = len(sheep)
    module.WHEAT_TILES = 0
    module.CASH_CROP_TILES = len(strawberries)
    module.COW_PURCHASE_BATCH = 3
    module.COW_HANDS = 11 if "_h11" in name else 12
    module.COW_FIRST_PURCHASE = "cowfirst" in name
    module.OPENING_ANIMAL = "COW"
    module.OPENING_ANIMAL_TARGET = 2
    module.OPENING_REPLANT = not name.endswith("_noreplant")
    module.crop_agent.TARGET_HANDS = 6
    module._apply_learned_macro_profile = lambda _obs: None
    module.crop_agent._plan = lambda _size, _expanded=False: dict(OPENING_PLAN)
    module._cow_targets = lambda _size: tuple(cows)
    module._sheep_targets = lambda _size: tuple(sheep)
    module._wheat_targets = lambda _size: ()
    module._cash_crop_targets = lambda _size: tuple(strawberries)
    original_agent = module.agent

    def scripted_agent(obs: dict[str, Any]):
        if int(obs.get("day", 0)) == 0:
            return DAY0_SCRIPT[str(int(obs.get("hour", 0)))]
        return original_agent(obs)

    return scripted_agent


def play(task: tuple[str, int, int, bool]) -> dict[str, Any]:
    name, seed, seat, fast = task
    suffix = f"{os.getpid()}_{name}_{seed}_{seat}"
    candidate_module = load_module(ROOT / "main.py", f"candidate_{suffix}")
    incumbent_module = load_module(ROOT / "main.py", f"incumbent_{suffix}")
    candidate = configure(candidate_module, name)
    agents = (
        [candidate, incumbent_module.agent]
        if seat == 0
        else [incumbent_module.agent, candidate]
    )
    if fast:
        final = run_fast_episode(agents, seed=seed)
    else:
        from kaggle_environments import make

        env = make(
            "kaggriculture",
            configuration={"episodeSteps": 720, "seed": seed},
            debug=False,
        )
        env.run(agents)
        final = env.steps[-1]
    reward = float(final[seat].reward)
    opponent_reward = float(final[1 - seat].reward)
    return {
        "variant": name,
        "seed": seed,
        "seat": seat,
        "reward": reward,
        "opponent_reward": opponent_reward,
        "margin": reward - opponent_reward,
        "win": reward > opponent_reward,
        "tie": reward == opponent_reward,
        "status": str(final[seat].status),
    }


def summarize(games: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "games": len(games),
        "wins": sum(game["win"] for game in games),
        "ties": sum(game["tie"] for game in games),
        "win_rate": mean(float(game["win"]) for game in games),
        "mean_reward": mean(game["reward"] for game in games),
        "mean_margin": mean(game["margin"] for game in games),
        "all_done": all(game["status"] == "DONE" for game in games),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-start", type=int, default=1_500_000)
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--variants", nargs="+", choices=sorted(VARIANTS), default=sorted(VARIANTS))
    parser.add_argument("--fast-runner", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    tasks = [
        (name, args.seed_start + index * 17, seat, args.fast_runner)
        for name in args.variants
        for index in range(args.seeds)
        for seat in (0, 1)
    ]
    games_by_variant = {name: [] for name in args.variants}
    context = mp.get_context("spawn")
    with context.Pool(max(1, min(args.workers, os.cpu_count() or args.workers))) as pool:
        for game in pool.imap_unordered(play, tasks, chunksize=1):
            games_by_variant[game["variant"]].append(game)

    results = [
        {
            "variant": name,
            "summary": summarize(games),
            "games": sorted(games, key=lambda game: (game["seed"], game["seat"])),
        }
        for name, games in games_by_variant.items()
    ]
    results.sort(
        key=lambda result: (
            result["summary"]["win_rate"],
            result["summary"]["mean_margin"],
        ),
        reverse=True,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    for result in results:
        summary = result["summary"]
        print(
            f"{result['variant']}: wins={summary['wins']}/{summary['games']} "
            f"ties={summary['ties']} reward={summary['mean_reward']:.1f} "
            f"margin={summary['mean_margin']:+.1f}"
        )


if __name__ == "__main__":
    main()

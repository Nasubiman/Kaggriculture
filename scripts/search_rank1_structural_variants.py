#!/usr/bin/env python3
"""Screen rank-1-inspired structural variants against the incumbent."""

from __future__ import annotations

import argparse
import importlib.util
import json
import multiprocessing as mp
import os
from pathlib import Path
from statistics import mean
from typing import Any

from kaggle_environments import make


ROOT = Path(__file__).resolve().parents[1]

COW_HEAVY_COWS = [
    (4, 0), (5, 0),
    (4, 1), (5, 1), (6, 1),
    (2, 2), (3, 2), (5, 2), (6, 2),
    (1, 3), (2, 3), (3, 3), (5, 3), (6, 3), (7, 3), (8, 3),
    (1, 4), (2, 4), (5, 4), (6, 4), (7, 4), (8, 4),
]
COW_HEAVY_SHEEP = [(3, 1), (4, 2), (7, 2), (4, 3), (3, 4), (4, 4)]
SHEEP_HEAVY_COWS = [
    (3, 1), (4, 1), (3, 2), (5, 2), (6, 2), (3, 3),
    (5, 3), (6, 3), (2, 4), (5, 4), (6, 4), (7, 4),
]
SHEEP_HEAVY_SHEEP = [
    (4, 0), (5, 0), (5, 1), (6, 1), (2, 2), (4, 2), (7, 2),
    (1, 3), (2, 3), (4, 3), (7, 3), (8, 3),
    (1, 4), (3, 4), (4, 4), (8, 4),
]

VARIANTS: dict[str, dict[str, Any]] = {
    "incumbent": {},
    **{
        f"sale_factor_{factor:02d}": {"factor_only": factor / 100}
        for factor in range(40, 50)
    },
    "dynamic_d10_staged": {
        "mode": "dynamic", "start": 10, "opening_hands": 3, "staged": True,
    },
    "dynamic_d9_staged": {
        "mode": "dynamic", "start": 9, "opening_hands": 3, "staged": True,
    },
    "dynamic_d8_staged": {
        "mode": "dynamic", "start": 8, "opening_hands": 3, "staged": True,
    },
    "dynamic_d10_current_hands": {
        "mode": "dynamic", "start": 10, "opening_hands": 7, "staged": False,
    },
    "cow22_d10_staged": {
        "mode": "cow", "start": 10, "opening_hands": 3, "staged": True,
    },
    "sheep16_d10_staged": {
        "mode": "sheep", "start": 10, "opening_hands": 3, "staged": True,
    },
    "cow22_d8_current_hands": {
        "mode": "cow", "start": 8, "opening_hands": 7, "staged": False,
    },
    "sheep16_d8_current_hands": {
        "mode": "sheep", "start": 8, "opening_hands": 7, "staged": False,
    },
    "incumbent_staged": {
        "mode": "incumbent", "start": 8, "opening_hands": 3, "staged": True,
    },
}


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def configure(module: Any, config: dict[str, Any]):
    if not config:
        return module.agent
    if "factor_only" in config:
        module.SALE_PROCEEDS_FACTOR = float(config["factor_only"])
        return module.agent

    original_agent = module.agent
    original_cow_targets = module._cow_targets
    original_sheep_targets = module._sheep_targets
    mode: str | None = None

    module.COW_START_DAY = int(config["start"])
    module.crop_agent.TARGET_HANDS = int(config["opening_hands"])

    def cow_targets(board_size: int):
        if mode == "cow":
            return COW_HEAVY_COWS
        if mode == "sheep":
            return SHEEP_HEAVY_COWS
        return original_cow_targets(board_size)

    def sheep_targets(board_size: int):
        if mode == "cow":
            return COW_HEAVY_SHEEP
        if mode == "sheep":
            return SHEEP_HEAVY_SHEEP
        return original_sheep_targets(board_size)

    module._cow_targets = cow_targets
    module._sheep_targets = sheep_targets

    def agent(obs):
        nonlocal mode
        day = int(obs.get("day", 0))
        hour = int(obs.get("hour", 0))
        if day == 0 and hour == 0:
            mode = None

        if day >= int(config["start"]):
            requested = config["mode"]
            if requested == "dynamic" and mode is None:
                prices = (obs.get("market", {}) or {}).get("prices", {}) or {}
                mode = (
                    "sheep"
                    if float(prices.get("MILK", 0))
                    >= float(prices.get("WOOL", 0))
                    else "cow"
                )
            elif requested in ("cow", "sheep"):
                mode = requested

        if mode == "cow":
            module.COW_TARGET = len(COW_HEAVY_COWS)
            module.SHEEP_TARGET = len(COW_HEAVY_SHEEP)
        elif mode == "sheep":
            module.COW_TARGET = len(SHEEP_HEAVY_COWS)
            module.SHEEP_TARGET = len(SHEEP_HEAVY_SHEEP)
        else:
            module.COW_TARGET = 16
            module.SHEEP_TARGET = 4

        if config.get("staged"):
            if day < int(config["start"]):
                module.crop_agent.TARGET_HANDS = 3 if day < 7 else 4
            elif day == int(config["start"]):
                module.COW_HANDS = 4
            elif day == int(config["start"]) + 1:
                module.COW_HANDS = 8
            elif day < 18:
                module.COW_HANDS = 11
            else:
                module.COW_HANDS = 12
        else:
            module.COW_HANDS = 11
        return original_agent(obs)

    return agent


def play(task: tuple[str, dict[str, Any], int, int]) -> dict[str, Any]:
    name, config, seed, seat = task
    suffix = f"{os.getpid()}_{name}_{seed}_{seat}"
    candidate_module = load_module(ROOT / "main.py", f"candidate_{suffix}")
    incumbent_module = load_module(ROOT / "main.py", f"incumbent_{suffix}")
    candidate = configure(candidate_module, config)
    agents = (
        [candidate, incumbent_module.agent]
        if seat == 0
        else [incumbent_module.agent, candidate]
    )
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
        "status": final[seat].status,
    }


def summarize(games: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "games": len(games),
        "wins": sum(game["win"] for game in games),
        "ties": sum(game["tie"] for game in games),
        "win_rate": mean(float(game["win"]) for game in games),
        "mean_reward": mean(game["reward"] for game in games),
        "mean_opponent_reward": mean(game["opponent_reward"] for game in games),
        "mean_margin": mean(game["margin"] for game in games),
        "all_done": all(game["status"] == "DONE" for game in games),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", nargs="+", type=int, required=True)
    parser.add_argument(
        "--variants", nargs="+", choices=sorted(VARIANTS), default=sorted(VARIANTS)
    )
    parser.add_argument("--workers", type=int, default=min(8, os.cpu_count() or 4))
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "reports" / "rank1_structural_search.json",
    )
    args = parser.parse_args()

    tasks = [
        (name, VARIANTS[name], seed, seat)
        for name in args.variants
        for seed in args.seeds
        for seat in (0, 1)
    ]
    games_by_variant = {name: [] for name in args.variants}
    context = mp.get_context("spawn")
    with context.Pool(max(1, args.workers)) as pool:
        for game in pool.imap_unordered(play, tasks, chunksize=1):
            games_by_variant[game["variant"]].append(game)
            print(
                f"{game['variant']} seed={game['seed']} seat={game['seat']} "
                f"margin={game['margin']:+.0f}",
                flush=True,
            )

    results = [
        {
            "variant": name,
            "config": VARIANTS[name],
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
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()

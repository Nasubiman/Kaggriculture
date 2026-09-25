#!/usr/bin/env python3
"""Ablate earlier land purchases without changing the incumbent work route."""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
from pathlib import Path

from kaggle_environments.agent import get_last_callable
from production_fast_kaggriculture import run_fast_episode


_BASE = None
_OPPONENTS = {}
VARIANTS = ("baseline", "third249", "third253", "third249_fourth265",
            "third253_fourth265")


def load(path: str):
    source = Path(path)
    return get_last_callable(source.read_text(encoding="utf-8"), path=str(source))


def init_worker(candidate: str, opponents: dict[str, str]) -> None:
    global _BASE, _OPPONENTS
    _BASE = load(candidate)
    _OPPONENTS = {name: load(path) for name, path in opponents.items()}


def wrap(variant: str, stats: dict):
    def candidate(observation):
        action = _BASE(observation)
        step = int(observation["step"])
        farm = observation["farms"][int(observation["player"])]
        if step in (249, 253, 265, 288, 360, 432):
            tiles = farm["tiles"]
            se = [tile for row in tiles[5:10] for tile in row[5:10]
                  if isinstance(tile, dict)]
            stats[f"step{step}"] = {
                "quadrants": len(farm["unlocked_quadrants"]),
                "cash": int(farm["money"]),
                "se_plants": sum(tile.get("kind") == "PLANT" for tile in se),
                "se_pastures": sum(tile.get("kind") == "PASTURE" for tile in se),
            }
        if variant == "baseline":
            return action
        quadrants = len(farm["unlocked_quadrants"])
        third_step = 249 if "third249" in variant else 253
        desired = (step == third_step and quadrants == 2) or (
            "fourth265" in variant and step == 265 and quadrants == 3)
        if not desired:
            return action
        market = [list(order) for order in action.get("market") or [] if order]
        if len(market) >= 10 or any(order[0] == "BUY_LAND" for order in market):
            return action
        market.append(["BUY_LAND"])
        stats["attempted"] += 1
        return dict(action, market=market)

    return candidate


def play(task: tuple[str, str, int, int]) -> dict:
    variant, opponent_name, seed, seat = task
    stats = {"attempted": 0}
    candidate = wrap(variant, stats)
    opponent = _OPPONENTS[opponent_name]
    agents = [candidate, opponent] if seat == 0 else [opponent, candidate]
    try:
        result = run_fast_episode(agents, seed=seed)
        ours = float(result[seat].reward)
        theirs = float(result[1 - seat].reward)
        quadrants = len(result[seat].observation["farms"][seat]["unlocked_quadrants"])
        error = None
    except Exception as exc:
        ours = theirs = 0.0
        quadrants = 0
        error = f"{type(exc).__name__}: {exc}"
    return {"variant": variant, "opponent": opponent_name, "seed": seed,
            "seat": seat, "reward": ours, "opponent_reward": theirs,
            "margin": ours - theirs, "win": ours > theirs,
            "quadrants": quadrants, "error": error, **stats}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, default=Path("main.py"))
    parser.add_argument("--models-dir", type=Path, default=Path("test"))
    parser.add_argument("--opponents", nargs="+", default=["results25_20260923", "results29_20260924"])
    parser.add_argument("--variants", nargs="+", choices=VARIANTS, default=VARIANTS)
    parser.add_argument("--seed-start", type=int, default=13095065)
    parser.add_argument("--seeds", type=int, default=30)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    opponents = {name: str((args.models_dir / name / "main.py").resolve())
                 for name in args.opponents}
    for path in opponents.values():
        if not Path(path).is_file():
            parser.error(f"missing opponent {path}")
    tasks = [(variant, name, args.seed_start + seed * 17, seat)
             for variant in args.variants for name in opponents
             for seed in range(args.seeds) for seat in (0, 1)]
    with mp.Pool(args.workers, initializer=init_worker,
                 initargs=(str(args.candidate.resolve()), opponents)) as pool:
        rows = list(pool.imap_unordered(play, tasks, chunksize=1))
    summary = {}
    for variant in args.variants:
        subset = [row for row in rows if row["variant"] == variant]
        summary[variant] = {
            "games": len(subset), "wins": sum(row["win"] for row in subset),
            "mean_reward": sum(row["reward"] for row in subset) / len(subset),
            "mean_margin": sum(row["margin"] for row in subset) / len(subset),
            "four_quadrant_games": sum(row["quadrants"] == 4 for row in subset),
            "attempted_orders": sum(row["attempted"] for row in subset),
            "errors": [row for row in subset if row["error"]],
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"summary": summary, "rows": rows}, indent=2),
                           encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

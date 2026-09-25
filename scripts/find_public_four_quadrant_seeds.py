#!/usr/bin/env python3
"""Find fresh paired-test seeds with milk-shop conditions and sufficient cash."""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
from collections import Counter
from pathlib import Path
from time import perf_counter

from kaggle_environments.agent import get_last_callable
from production_fast_kaggriculture import create_fast_episode, run_fast_steps


_AGENTS = None


def init_worker(candidate: str) -> None:
    global _AGENTS
    source = Path(candidate).read_text(encoding="utf-8")
    _AGENTS = [get_last_callable(source, path=candidate) for _ in range(2)]


def inspect(seed: int) -> dict:
    env, state = create_fast_episode(seed=seed)
    state = run_fast_steps(_AGENTS, env=env, state=state, stop_step=144)
    shops = list(state[0].observation["town"]["unlocked_shops"])
    milk = {"ICE_CREAM_SHOP", "SMOOTHIE_SHOP", "PIZZA_SHOP"}
    if len(set(shops) & milk) < 2:
        return {"seed": seed, "shops": shops, "milk_two": False, "eligible": False}
    state = run_fast_steps(_AGENTS, env=env, state=state, stop_step=289)
    observation = state[0].observation
    farm = observation["farms"][0]
    prices = observation["market"]["prices"]
    return {"seed": seed, "shops": shops, "milk_two": True,
            "ice_smoothie": {"ICE_CREAM_SHOP", "SMOOTHIE_SHOP"}.issubset(shops),
            "cash": float(farm["money"]),
            "prices": {name: float(value) for name, value in prices.items()},
            "quadrants": len(farm["unlocked_quadrants"]),
            "eligible": len(farm["unlocked_quadrants"]) == 3 and farm["money"] >= 10000}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, default=Path("main.py"))
    parser.add_argument("--seed-start", type=int, default=123_000_000)
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    started = perf_counter()
    seeds = [args.seed_start + 17 * i for i in range(args.count)]
    with mp.get_context("spawn").Pool(args.workers, initializer=init_worker,
                                       initargs=(str(args.candidate.resolve()),)) as pool:
        rows = list(pool.imap_unordered(inspect, seeds, chunksize=1))
    selected = sorted((row for row in rows if row["eligible"]), key=lambda row: row["seed"])
    output = {"seed_start": args.seed_start, "count": args.count,
              "elapsed_seconds": perf_counter()-started,
              "shop_pairs": dict(Counter(" + ".join(row["shops"]) for row in rows)),
              "eligible": selected}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(f"scanned={len(rows)} milk_two={sum(row['milk_two'] for row in rows)} "
          f"eligible={len(selected)} ice_smoothie={sum(row['ice_smoothie'] for row in selected)} "
          f"elapsed={perf_counter()-started:.1f}s")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()

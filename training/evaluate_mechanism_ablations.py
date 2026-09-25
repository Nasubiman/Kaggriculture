#!/usr/bin/env python3
"""Measure the paired value of each wrapper in a layered public agent.

The public agents in this competition are commonly built by repeatedly saving
``agent`` in a ``*_PARENT`` global and installing a new wrapper.  Rewiring the
next wrapper's parent bypasses exactly one layer while preserving all later
layers, which gives a much more useful signal than comparing whole releases.
"""

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


_BASE = ""
_OPPONENTS: dict[str, str] = {}
_AGENT_CACHE: dict[str, Any] = {}
_RIVAL_CACHE: dict[str, Any] = {}


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parent_chain(module: Any) -> list[str]:
    return [
        name for name, value in vars(module).items()
        if "PARENT" in name and name.endswith("_PARENT") and callable(value)
    ]


def mechanism_agent(path: Path, disabled: str):
    module = load_module(path, f"mechanism_{os.getpid()}_{disabled}")
    if disabled == "full":
        return module.agent
    chain = parent_chain(module)
    if disabled not in chain:
        raise KeyError(f"unknown layer {disabled}; available={chain}")
    index = chain.index(disabled)
    if index == len(chain) - 1:
        return getattr(module, disabled)
    # The next wrapper normally calls the target wrapper. Point it at the
    # target's own parent instead, removing only the target layer.
    setattr(module, chain[index + 1], getattr(module, disabled))
    return module.agent


def worker_init(base: str, opponents: dict[str, str]):
    global _BASE, _OPPONENTS, _AGENT_CACHE, _RIVAL_CACHE
    _BASE, _OPPONENTS = base, opponents
    _AGENT_CACHE, _RIVAL_CACHE = {}, {}


def play(task: tuple[str, str, int, int]):
    variant, opponent, seed, seat = task
    try:
        agent = _AGENT_CACHE.get(variant)
        if agent is None:
            agent = mechanism_agent(Path(_BASE), variant)
            _AGENT_CACHE[variant] = agent
        rival = _RIVAL_CACHE.get(opponent)
        if rival is None:
            rival = load_module(Path(_OPPONENTS[opponent]),
                                f"rival_{os.getpid()}_{opponent}").agent
            _RIVAL_CACHE[opponent] = rival
        agents = [agent, rival] if seat == 0 else [rival, agent]
        final = run_fast_episode(agents, seed=seed)
        reward = float(final[seat].reward)
        rival_reward = float(final[1 - seat].reward)
        return {"variant": variant, "opponent": opponent, "seed": seed,
                "seat": seat, "reward": reward,
                "margin": reward - rival_reward, "error": None}
    except Exception as error:
        return {"variant": variant, "opponent": opponent, "seed": seed,
                "seat": seat, "reward": -1_000_000.0,
                "margin": -1_000_000.0, "error": repr(error)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--models-dir", type=Path, default=Path("test"))
    parser.add_argument("--opponents", nargs="+", required=True)
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--seed-start", type=int, default=24_100_000)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    probe = load_module(args.base.resolve(), "mechanism_probe")
    variants = ["full", *parent_chain(probe)]
    paths = {name: (args.models_dir / name / "main.py").resolve()
             for name in args.opponents}
    missing = [path for path in [args.base, *paths.values()] if not path.is_file()]
    if missing:
        raise SystemExit("missing: " + ", ".join(map(str, missing)))
    seeds = [args.seed_start + 31 * index for index in range(args.seeds)]
    tasks = [(variant, opponent, seed, seat) for variant in variants
             for opponent in args.opponents for seed in seeds for seat in (0, 1)]
    games = {variant: [] for variant in variants}
    context = mp.get_context("spawn")
    with context.Pool(min(args.workers, os.cpu_count() or args.workers),
                      initializer=worker_init,
                      initargs=(str(args.base.resolve()),
                                {name: str(path) for name, path in paths.items()})) as pool:
        for result in pool.imap_unordered(play, tasks, chunksize=1):
            games[result["variant"]].append(result)

    baseline = {(game["opponent"], game["seed"], game["seat"]): game
                for game in games["full"]}
    summaries = []
    for variant in variants:
        rows = games[variant]
        reward_deltas = [row["reward"] - baseline[
            (row["opponent"], row["seed"], row["seat"])]["reward"] for row in rows]
        margin_deltas = [row["margin"] - baseline[
            (row["opponent"], row["seed"], row["seat"])]["margin"] for row in rows]
        by_opponent = {}
        for opponent in args.opponents:
            subset = [row for row in rows if row["opponent"] == opponent]
            by_opponent[opponent] = {
                "reward_delta": mean(row["reward"] - baseline[
                    (opponent, row["seed"], row["seat"])]["reward"] for row in subset),
                "margin_delta": mean(row["margin"] - baseline[
                    (opponent, row["seed"], row["seat"])]["margin"] for row in subset),
            }
        summaries.append({"variant": variant, "games": len(rows),
                          "mean_reward_delta": mean(reward_deltas),
                          "mean_margin_delta": mean(margin_deltas),
                          "errors": sum(row["error"] is not None for row in rows),
                          "by_opponent": by_opponent})
    summaries.sort(key=lambda row: row["mean_reward_delta"])
    payload = {"base": str(args.base.resolve()), "opponents": args.opponents,
               "seeds": seeds, "parent_chain": variants[1:], "summaries": summaries}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n")
    for row in summaries:
        print(f"{row['variant']:28s} reward={row['mean_reward_delta']:+8.1f} "
              f"margin={row['mean_margin_delta']:+8.1f} errors={row['errors']}")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()

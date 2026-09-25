#!/usr/bin/env python3
"""Paired test of early-market ideas observed in a recent public replay.

The 2026-09-22 DSM/Vadim episode 111896997 bought a cow and wheat at step 0,
then bought another cow and three sheep with four hires at step 1. These are
ablation candidates, not claims that the observed actions generalize.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
from collections import defaultdict
from pathlib import Path
from time import perf_counter

from kaggle_environments.agent import get_last_callable
from production_fast_kaggriculture import run_fast_episode


VARIANTS = ("baseline", "cow_step0", "cow_step0_step1", "cow_step0_four_hires")
_CANDIDATE = None
_OPPONENTS = {}


def load_agent(path: Path):
    agent = get_last_callable(path.read_text(encoding="utf-8"), path=str(path))
    if not callable(agent):
        raise RuntimeError(f"no callable entry point: {path}")
    return agent


def init_worker(candidate: str, opponents: dict[str, str]) -> None:
    global _CANDIDATE, _OPPONENTS
    _CANDIDATE = load_agent(Path(candidate))
    _OPPONENTS = {name: load_agent(Path(path)) for name, path in opponents.items()}


def candidate_action(observation, variant: str):
    action = _CANDIDATE(observation)
    step = int(observation["step"])
    if variant == "baseline" or step > 1:
        return action
    if step == 0:
        return dict(action, market=[["BUY_ANIMAL", "COW", 1], ["BUY_PRODUCT", "WHEAT", 5]])
    if variant == "cow_step0":
        return action
    if variant == "cow_step0_step1":
        return dict(action, market=[
            ["SELL", "WHEAT", 1], ["HIRE"], ["HIRE"], ["HIRE"], ["HIRE"],
            ["BUY_ANIMAL", "COW", 1], ["BUY_ANIMAL", "SHEEP", 3],
        ])
    # Preserve the current model's animal purchases but reduce the day-0
    # worker count to the four used in the public replay.
    market = [order for order in action.get("market", []) if order and order[0] != "HIRE"]
    return dict(action, market=[["HIRE"] for _ in range(4)] + market)


def play(task: tuple[str, str, int, int]) -> dict:
    variant, opponent_name, seed, seat = task
    opponent = _OPPONENTS[opponent_name]
    def candidate(observation):
        return candidate_action(observation, variant)
    agents = [candidate, opponent] if seat == 0 else [opponent, candidate]
    try:
        result = run_fast_episode(agents, seed=seed)
        ours = float(result[seat].reward)
        theirs = float(result[1 - seat].reward)
        error = None
    except Exception as exc:
        ours = theirs = 0.0
        error = f"{type(exc).__name__}: {exc}"
    return {"variant": variant, "opponent": opponent_name, "seed": seed,
            "seat": seat, "reward": ours, "opponent_reward": theirs,
            "margin": ours - theirs, "win": ours > theirs, "error": error}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, default=Path("main.py"))
    parser.add_argument("--models-dir", type=Path, default=Path("test"))
    parser.add_argument("--opponents", nargs="+", required=True)
    parser.add_argument("--variants", nargs="+", choices=VARIANTS, default=VARIANTS)
    parser.add_argument("--seed-start", type=int, default=123_000_000)
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.seeds < 1 or args.workers < 1:
        parser.error("seeds and workers must be positive")
    opponents = {name: str((args.models_dir / name / "main.py").resolve())
                 for name in args.opponents}
    missing = [name for name, path in opponents.items() if not Path(path).is_file()]
    if missing:
        parser.error(f"missing opponents: {missing}")
    tasks = [(variant, name, args.seed_start + 17 * offset, seat)
             for offset in range(args.seeds) for name in args.opponents
             for seat in (0, 1) for variant in args.variants]
    started = perf_counter()
    games = []
    with mp.get_context("spawn").Pool(args.workers, initializer=init_worker,
                                       initargs=(str(args.candidate.resolve()), opponents)) as pool:
        for index, row in enumerate(pool.imap_unordered(play, tasks, chunksize=1), 1):
            games.append(row)
            if index % 200 == 0:
                print(f"completed={index}/{len(tasks)} elapsed={perf_counter()-started:.1f}s", flush=True)
    summary = {}
    for variant in args.variants:
        rows = [row for row in games if row["variant"] == variant]
        by_opponent = {}
        for name in args.opponents:
            subset = [row for row in rows if row["opponent"] == name]
            by_opponent[name] = {"wins": sum(row["win"] for row in subset),
                                 "games": len(subset),
                                 "mean_margin": sum(row["margin"] for row in subset) / len(subset),
                                 "errors": sum(row["error"] is not None for row in subset)}
        summary[variant] = {"wins": sum(row["win"] for row in rows),
                            "games": len(rows),
                            "mean_margin": sum(row["margin"] for row in rows) / len(rows),
                            "errors": sum(row["error"] is not None for row in rows),
                            "per_opponent": by_opponent}
    output = {"source_episode": 111896997, "candidate": str(args.candidate),
              "seed_start": args.seed_start, "seeds": args.seeds,
              "workers": args.workers, "elapsed_seconds": perf_counter()-started,
              "summaries": summary,
              "games": sorted(games, key=lambda row: (row["variant"], row["opponent"], row["seed"], row["seat"]))}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    for variant in args.variants:
        row = summary[variant]
        print(f"{variant}: wins={row['wins']}/{row['games']} "
              f"margin={row['mean_margin']:+.1f} errors={row['errors']}", flush=True)
    print(f"wrote {args.output}", flush=True)


if __name__ == "__main__":
    main()

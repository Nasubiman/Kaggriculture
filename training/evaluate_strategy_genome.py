#!/usr/bin/env python3
"""Evaluate one structured strategy genome on fixed seeds and both seats."""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
from pathlib import Path

from search_structured_strategies import ROOT, play_task, summarize, worker_init
from strategy_genome import StrategyGenome


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--genome", type=Path, required=True)
    parser.add_argument("--opponent", type=Path, default=ROOT / "main.py")
    parser.add_argument("--seed-start", type=int, default=9_100_000)
    parser.add_argument("--seeds", type=int, default=100)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument(
        "--fast-runner", action=argparse.BooleanOptionalAction, default=True
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    genome = StrategyGenome(
        **json.loads(args.genome.read_text(encoding="utf-8"))
    ).normalized()
    seed_values = [args.seed_start + index * 17 for index in range(args.seeds)]
    tasks = [
        (genome.to_dict(), seed, seat)
        for seed in seed_values
        for seat in (0, 1)
    ]
    workers = max(1, min(args.workers, os.cpu_count() or args.workers))
    context = mp.get_context("spawn")
    with context.Pool(
        workers,
        initializer=worker_init,
        initargs=(str(ROOT), str(args.opponent.resolve()), args.fast_runner),
    ) as pool:
        games = list(pool.imap_unordered(play_task, tasks, chunksize=1))
    result = {
        "genome": genome.to_dict(),
        "opponent": str(args.opponent.resolve()),
        "fast_runner": args.fast_runner,
        "summary": summarize(genome, games),
        "games": sorted(games, key=lambda game: (game["seed"], game["seat"])),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2), flush=True)


if __name__ == "__main__":
    main()

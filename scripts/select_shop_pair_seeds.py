#!/usr/bin/env python3
"""Find independent seeds with a chosen first-two-shop combination at day six."""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
from pathlib import Path

from kaggle_environments.agent import get_last_callable
from production_fast_kaggriculture import create_fast_episode, run_fast_steps


_AGENTS = None


def setup(candidate, opponent):
    global _AGENTS
    paths = (Path(candidate), Path(opponent))
    _AGENTS = [get_last_callable(path.read_text(encoding="utf-8"), path=str(path))
               for path in paths]


def check(seed):
    env, state = create_fast_episode(seed=seed)
    final = run_fast_steps(_AGENTS, env=env, state=state, stop_step=144)
    pair = list(final[0].observation.town.unlocked_shops[:2])
    return seed, pair


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--opponent", type=Path, required=True)
    parser.add_argument("--shops", nargs=2, required=True)
    parser.add_argument("--seed-start", type=int, required=True)
    parser.add_argument("--seed-count", type=int, default=500)
    parser.add_argument("--workers", type=int, default=20)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    seeds = range(args.seed_start, args.seed_start + args.seed_count)
    ctx = mp.get_context("spawn")
    with ctx.Pool(min(args.workers, os.cpu_count() or 1), initializer=setup,
                  initargs=(str(args.candidate), str(args.opponent))) as pool:
        matches = [seed for seed, pair in pool.imap_unordered(check, seeds, chunksize=1)
                   if pair == args.shops]
    matches.sort()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(matches) + "\n", encoding="utf-8")
    print(f"found {len(matches)}/{args.seed_count} seeds for {args.shops}: {args.output}")


if __name__ == "__main__":
    main()

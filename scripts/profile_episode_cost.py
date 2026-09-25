#!/usr/bin/env python3
"""Measure policy and runner wall time in production evaluation episodes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import perf_counter

from kaggle_environments.agent import get_last_callable
from production_fast_kaggriculture import run_fast_episode


def load_raw_agent(path: Path):
    selected = get_last_callable(path.read_text(encoding="utf-8"), path=str(path))
    if not callable(selected):
        raise RuntimeError(f"{path} has no callable entry point")
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, default=Path("main.py"))
    parser.add_argument("--opponent", type=Path, default=Path("test/results29_20260924/main.py"))
    parser.add_argument("--seeds", type=int, default=8)
    parser.add_argument("--seed-start", type=int, default=115_000_000)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.seeds < 1:
        parser.error("--seeds must be positive")

    candidate = load_raw_agent(args.candidate)
    opponent = load_raw_agent(args.opponent)
    rows = []
    for index in range(args.seeds + 1):
        seed = args.seed_start + 17 * index
        seat = index % 2
        agent_seconds = [0.0, 0.0]
        calls = [0, 0]

        def timed(agent, actor):
            def call(observation):
                started = perf_counter()
                try:
                    return agent(observation)
                finally:
                    agent_seconds[actor] += perf_counter() - started
                    calls[actor] += 1
            return call

        agents = [candidate, opponent] if seat == 0 else [opponent, candidate]
        wrapped = [timed(agent, actor) for actor, agent in enumerate(agents)]
        started = perf_counter()
        final = run_fast_episode(wrapped, seed=seed)
        total = perf_counter() - started
        if any(str(entry.status) != "DONE" for entry in final):
            raise RuntimeError(f"unfinished episode: seed={seed}")
        if index == 0:  # warm up imports, caches, and native modules
            continue
        policy = sum(agent_seconds)
        rows.append({
            "seed": seed,
            "seat": seat,
            "total_seconds": total,
            "candidate_seconds": agent_seconds[seat],
            "opponent_seconds": agent_seconds[1 - seat],
            "runner_and_wrapper_seconds": total - policy,
            "calls": calls,
            "rewards": [float(entry.reward) for entry in final],
        })

    aggregate = {
        "games": len(rows),
        "total_seconds": sum(row["total_seconds"] for row in rows),
        "candidate_seconds": sum(row["candidate_seconds"] for row in rows),
        "opponent_seconds": sum(row["opponent_seconds"] for row in rows),
        "runner_and_wrapper_seconds": sum(row["runner_and_wrapper_seconds"] for row in rows),
    }
    aggregate["runner_fraction"] = aggregate["runner_and_wrapper_seconds"] / aggregate["total_seconds"]
    aggregate["max_speedup_from_runner_only"] = 1 / (1 - aggregate["runner_fraction"])
    result = {"candidate": str(args.candidate), "opponent": str(args.opponent),
              "aggregate": aggregate, "games": rows}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(aggregate, indent=2))


if __name__ == "__main__":
    main()

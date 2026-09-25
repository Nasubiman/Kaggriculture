#!/usr/bin/env python3
"""Compare two agents on identical full episodes with the production runner.

This measures single-process wall time with agent instances reused across games,
matching the evaluation workers. Rewards must agree for every seed and seat.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from pathlib import Path
from time import perf_counter

from kaggle_environments.agent import get_last_callable
from production_fast_kaggriculture import run_fast_episode


def load_raw_agent(path: Path):
    agent = get_last_callable(path.read_text(encoding="utf-8"), path=str(path))
    if not callable(agent):
        raise RuntimeError(f"{path} does not define a callable entry point")
    return agent


def run_game(agent, opponent, seed: int, seat: int) -> tuple[float, tuple[float, ...]]:
    lineup = [agent, opponent] if seat == 0 else [opponent, agent]
    started = perf_counter()
    final = run_fast_episode(lineup, seed=seed)
    return perf_counter() - started, tuple(float(entry.reward) for entry in final)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--opponent", type=Path, required=True)
    parser.add_argument("--seeds", type=int, default=8)
    parser.add_argument("--seed-start", type=int, default=94_000_000)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.seeds < 1 or args.repeats < 1:
        parser.error("seeds and repeats must be positive")

    baseline = load_raw_agent(args.baseline)
    candidate = load_raw_agent(args.candidate)
    opponent = load_raw_agent(args.opponent)
    agents = {"baseline": baseline, "candidate": candidate}
    tasks = [(args.seed_start + offset, seat)
             for offset in range(args.seeds) for seat in (0, 1)]
    for agent in agents.values():
        run_game(agent, opponent, *tasks[0])

    samples: dict[str, list[float]] = {name: [] for name in agents}
    for repeat in range(args.repeats):
        for seed, seat in tasks:
            names = ("baseline", "candidate") if (repeat + seed + seat) % 2 == 0 else ("candidate", "baseline")
            rewards = None
            for name in names:
                elapsed, result = run_game(agents[name], opponent, seed, seat)
                if rewards is not None and result != rewards:
                    raise AssertionError(f"reward mismatch: seed={seed} seat={seat}")
                rewards = result
                samples[name].append(elapsed)

    totals = {name: sum(values) for name, values in samples.items()}
    report = {
        "baseline": str(args.baseline),
        "candidate": str(args.candidate),
        "opponent": str(args.opponent),
        "seeds": args.seeds,
        "seed_start": args.seed_start,
        "repeats": args.repeats,
        "games_per_variant": len(samples["baseline"]),
        "source_sha256": {
            str(path): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (args.baseline, args.candidate, args.opponent)
        },
        "seconds": totals,
        "median_seconds": {name: statistics.median(values) for name, values in samples.items()},
        "speedup": totals["baseline"] / totals["candidate"],
        "reward_parity": True,
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

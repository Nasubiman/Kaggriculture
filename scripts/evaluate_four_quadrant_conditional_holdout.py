#!/usr/bin/env python3
"""Paired random-seed comparison of multiple conditional 4Q quantity policies.

Non-eligible games are action-identical to main.py, so they are screened at
step 290 rather than needlessly finished once per variant. An audit sample is
finished to verify this assumption. Each eligible game finishes a baseline
episode and one episode per requested variant on the same seed and seat.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import random
from collections import defaultdict
from pathlib import Path
from time import perf_counter

from production_fast_kaggriculture import create_fast_episode, run_fast_episode, run_fast_steps
import evaluate_four_quadrant_random as baseline_study
import search_public_four_quadrant as study


def init_worker(candidate: str, opponents: dict[str, str], tape: str) -> None:
    study.init_worker(candidate, opponents, tape)


def play(task: tuple[int, str, int, float, int, tuple[str, ...]]) -> dict:
    seed, opponent_name, seat, threshold, audit_mod, variants = task
    potential_steps: list[int] = []

    def baseline(observation):
        if baseline_study.probe_gate(observation, threshold):
            potential_steps.append(int(observation["step"]))
        return study._CANDIDATE(observation)

    opponent = study._OPPONENTS[opponent_name]
    agents = [baseline, opponent] if seat == 0 else [opponent, baseline]
    env, state = create_fast_episode(seed=seed)
    state = run_fast_steps(agents, env=env, state=state, stop_step=290)
    potential = bool(potential_steps)
    audit = (seed + 31 * seat + sum(map(ord, opponent_name))) % audit_mod == 0
    if not potential and not audit:
        return {"seed": seed, "opponent": opponent_name, "seat": seat,
                "potential_steps": [], "audit": False, "screened_only": True}
    state = run_fast_steps(agents, env=env, state=state, stop_step=719)
    baseline_reward = float(state[seat].reward)
    baseline_opponent_reward = float(state[1 - seat].reward)
    candidates = {}
    for variant in variants:
        stats = {"activated": 0}
        candidate = study.wrap_candidate(variant, threshold, stats)
        agents = [candidate, opponent] if seat == 0 else [opponent, candidate]
        result = run_fast_episode(agents, seed=seed)
        reward = float(result[seat].reward)
        opponent_reward = float(result[1 - seat].reward)
        if not potential and (reward != baseline_reward or opponent_reward != baseline_opponent_reward):
            raise AssertionError(f"ungated candidate differs: {seed=} {seat=} {opponent_name=} {variant=}")
        candidates[variant] = {
            "reward": reward, "opponent_reward": opponent_reward,
            "win": reward > opponent_reward,
            "margin": reward - opponent_reward,
            "activated": stats["activated"],
            "selected_strawberry_cap": stats.get("selected_strawberry_cap"),
            "strawberry_price_at_activation": stats.get("strawberry_price_at_activation"),
            "cash_at_activation": stats.get("cash_at_activation"),
            "shops_at_activation": stats.get("shops_at_activation"),
        }
    return {"seed": seed, "opponent": opponent_name, "seat": seat,
            "potential_steps": potential_steps, "audit": audit,
            "screened_only": False, "baseline_reward": baseline_reward,
            "baseline_opponent_reward": baseline_opponent_reward,
            "baseline_win": baseline_reward > baseline_opponent_reward,
            "baseline_margin": baseline_reward - baseline_opponent_reward,
            "candidates": candidates}


def summarize(rows: list[dict], variant: str) -> dict:
    completed = [row for row in rows if not row["screened_only"]]
    return {
        "games": len(rows),
        "potential": sum(bool(row["potential_steps"]) for row in rows),
        "completed_paired_games": len(completed),
        "audits": sum(row["audit"] and not row["potential_steps"] for row in rows),
        "activated": sum(row["candidates"][variant]["activated"] for row in completed),
        "delta_wins": sum(int(row["candidates"][variant]["win"])
                          - int(row["baseline_win"]) for row in completed),
        "delta_mean_margin": sum(row["candidates"][variant]["margin"]
                                 - row["baseline_margin"] for row in completed) / len(rows),
        "delta_mean_reward": sum(row["candidates"][variant]["reward"]
                                 - row["baseline_reward"] for row in completed) / len(rows),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, default=Path("main.py"))
    parser.add_argument("--tape", type=Path, default=Path("training/decem_se_strawberry_111847040.json"))
    parser.add_argument("--models-dir", type=Path, default=Path("test"))
    parser.add_argument("--opponents", nargs="+", required=True)
    parser.add_argument("--variants", nargs="+", choices=study.VARIANTS, required=True)
    parser.add_argument("--random-seed", type=int, default=20260930)
    parser.add_argument("--seeds", type=int, default=1000)
    parser.add_argument("--seed-values", nargs="+", type=int,
                        help="explicit seeds for a small smoke test")
    parser.add_argument("--min-cash", type=float, default=10_000)
    parser.add_argument("--audit-mod", type=int, default=127)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if min(args.seeds, args.audit_mod, args.workers) < 1:
        parser.error("seeds, audit-mod and workers must be positive")
    opponents = {name: str((args.models_dir / name / "main.py").resolve())
                 for name in args.opponents}
    for name, path in opponents.items():
        if not Path(path).is_file():
            parser.error(f"missing opponent: {name} ({path})")
    seeds = args.seed_values or random.Random(args.random_seed).sample(range(2**31), args.seeds)
    tasks = [(seed, name, seat, args.min_cash, args.audit_mod, tuple(args.variants))
             for seed in seeds for name in opponents for seat in (0, 1)]
    started = perf_counter()
    rows = []
    with mp.get_context("spawn").Pool(args.workers, initializer=init_worker,
                                      initargs=(str(args.candidate.resolve()), opponents,
                                                str(args.tape.resolve()))) as pool:
        for index, row in enumerate(pool.imap_unordered(play, tasks, chunksize=2), 1):
            rows.append(row)
            if index % 500 == 0:
                print(f"completed={index}/{len(tasks)} elapsed={perf_counter()-started:.1f}s",
                      flush=True)
    by_opponent: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_opponent[row["opponent"]].append(row)
    result = {
        "random_seed": args.random_seed, "seeds": seeds,
        "opponents": args.opponents, "variants": args.variants,
        "workers": args.workers, "elapsed_seconds": perf_counter()-started,
        "overall": {variant: summarize(rows, variant) for variant in args.variants},
        "by_opponent": {name: {variant: summarize(subset, variant)
                              for variant in args.variants}
                        for name, subset in by_opponent.items()},
        "games": sorted(rows, key=lambda row: (row["seed"], row["opponent"], row["seat"])),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["overall"], indent=2), flush=True)
    print(f"wrote {args.output}", flush=True)


if __name__ == "__main__":
    main()

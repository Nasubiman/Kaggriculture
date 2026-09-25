#!/usr/bin/env python3
"""Paired, unfiltered random-seed test of the experimental fourth-quadrant route.

The candidate is action-identical to main.py unless its step-253 or step-289
gate fires. We run every baseline game, and run the candidate only for games
whose baseline observation meets either gate. A deterministic sample of the
otherwise skipped games is rerun as an identity audit.
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
import search_public_four_quadrant as study


VARIANT = "early_ice_smoothie_high_prices"


def init_worker(candidate: str, opponents: dict[str, str], tape: str) -> None:
    study.init_worker(candidate, opponents, tape)


def probe_gate(observation, threshold: float) -> bool:
    step = int(observation["step"])
    if step not in (253, 289):
        return False
    farm = observation["farms"][int(observation["player"])]
    needed_quadrants = 2 if step == 253 else 3
    if len(farm["unlocked_quadrants"]) != needed_quadrants or farm["money"] < threshold:
        return False
    shops = set(observation["town"]["unlocked_shops"])
    if not {"ICE_CREAM_SHOP", "SMOOTHIE_SHOP"}.issubset(shops):
        return False
    prices = observation["market"]["prices"]
    strawberry, milk = (200, 220) if step == 253 else (210, 225)
    return prices["STRAWBERRY"] >= strawberry and prices["MILK"] >= milk


def play(task: tuple[int, str, int, float, int, str, bool]) -> dict:
    seed, opponent_name, seat, threshold, audit_mod, variant, screen_only = task
    potential_steps: list[int] = []

    def baseline(observation):
        if probe_gate(observation, threshold):
            potential_steps.append(int(observation["step"]))
        return study._CANDIDATE(observation)

    opponent = study._OPPONENTS[opponent_name]
    agents = [baseline, opponent] if seat == 0 else [opponent, baseline]
    audit = (seed + 31 * seat + sum(map(ord, opponent_name))) % audit_mod == 0
    if screen_only:
        env, state = create_fast_episode(seed=seed)
        run_fast_steps(agents, env=env, state=state, stop_step=290)
        screened_steps = tuple(potential_steps)
        if not potential_steps and not audit:
            return {"seed": seed, "opponent": opponent_name, "seat": seat,
                    "potential_steps": [], "audit": False, "activated": 0,
                    "identical": True, "screened_only": True}
        potential_steps.clear()
    first = run_fast_episode(agents, seed=seed)
    if screen_only and tuple(potential_steps) != screened_steps:
        raise AssertionError(f"gate screen/full mismatch: {seed=} {opponent_name=} {seat=}")
    baseline_ours = float(first[seat].reward)
    baseline_theirs = float(first[1 - seat].reward)
    stats = {"activated": 0}
    if potential_steps or audit:
        candidate = study.wrap_candidate(variant, threshold, stats)
        agents = [candidate, opponent] if seat == 0 else [opponent, candidate]
        second = run_fast_episode(agents, seed=seed)
        candidate_ours = float(second[seat].reward)
        candidate_theirs = float(second[1 - seat].reward)
    else:
        candidate_ours, candidate_theirs = baseline_ours, baseline_theirs
    identical = (baseline_ours == candidate_ours and baseline_theirs == candidate_theirs)
    if audit and not potential_steps and not identical:
        raise AssertionError(f"ungated candidate differed from baseline: {seed=} {opponent_name=} {seat=}")
    return {
        "seed": seed, "opponent": opponent_name, "seat": seat,
        "potential_steps": potential_steps, "audit": audit,
        "activated": stats["activated"], "identical": identical,
        "selected_strawberry_cap": stats.get("selected_strawberry_cap"),
        "strawberry_price_at_activation": stats.get("strawberry_price_at_activation"),
        "cash_at_activation": stats.get("cash_at_activation"),
        "screened_only": False,
        "baseline_reward": baseline_ours, "baseline_opponent_reward": baseline_theirs,
        "candidate_reward": candidate_ours, "candidate_opponent_reward": candidate_theirs,
        "baseline_win": baseline_ours > baseline_theirs,
        "candidate_win": candidate_ours > candidate_theirs,
        "baseline_margin": baseline_ours - baseline_theirs,
        "candidate_margin": candidate_ours - candidate_theirs,
    }


def summarize(rows: list[dict]) -> dict:
    n = len(rows)
    completed = [row for row in rows if not row["screened_only"]]
    if not completed:
        raise ValueError("no completed paired games")
    return {
        "games": n,
        "completed_paired_games": len(completed),
        "potential": sum(bool(row["potential_steps"]) for row in rows),
        "activated": sum(row["activated"] for row in rows),
        "audits": sum(row["audit"] and not row["potential_steps"] for row in rows),
        "changed": sum(not row["identical"] for row in rows),
        "baseline_wins_on_completed": sum(row["baseline_win"] for row in completed),
        "candidate_wins_on_completed": sum(row["candidate_win"] for row in completed),
        "delta_wins_all_screened": sum(int(row["candidate_win"])-int(row["baseline_win"])
                                       for row in completed),
        "delta_mean_margin_all_screened": sum(row["candidate_margin"]-row["baseline_margin"]
                                               for row in completed) / n,
        "delta_mean_reward_all_screened": sum(row["candidate_reward"]-row["baseline_reward"]
                                               for row in completed) / n,
        "baseline_wins": (sum(row["baseline_win"] for row in completed)
                          if len(completed) == n else None),
        "candidate_wins": (sum(row["candidate_win"] for row in completed)
                           if len(completed) == n else None),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, default=Path("main.py"))
    parser.add_argument("--tape", type=Path, default=Path("training/decem_se_strawberry_111847040.json"))
    parser.add_argument("--models-dir", type=Path, default=Path("test"))
    parser.add_argument("--opponents", nargs="+", required=True)
    parser.add_argument("--random-seed", type=int, default=20260924)
    parser.add_argument("--seeds", type=int, default=1000)
    parser.add_argument("--min-cash", type=float, default=10_000)
    parser.add_argument("--audit-mod", type=int, default=127)
    parser.add_argument("--variant", choices=study.VARIANTS, default=VARIANT)
    parser.add_argument("--screen-only", action="store_true",
                        help="stop non-gated baseline games at step 290; report exact win delta")
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
    seeds = random.Random(args.random_seed).sample(range(2**31), args.seeds)
    tasks = [(seed, name, seat, args.min_cash, args.audit_mod,
              args.variant, args.screen_only)
             for seed in seeds for name in args.opponents for seat in (0, 1)]
    started = perf_counter()
    games: list[dict] = []
    with mp.get_context("spawn").Pool(args.workers, initializer=init_worker,
                                       initargs=(str(args.candidate.resolve()), opponents,
                                                 str(args.tape.resolve()))) as pool:
        for index, row in enumerate(pool.imap_unordered(play, tasks, chunksize=2), 1):
            games.append(row)
            if index % 500 == 0:
                print(f"completed={index}/{len(tasks)} elapsed={perf_counter()-started:.1f}s", flush=True)
    by_opponent: dict[str, list[dict]] = defaultdict(list)
    for row in games:
        by_opponent[row["opponent"]].append(row)
    result = {
        "variant": args.variant, "random_seed": args.random_seed,
        "sampled_seed_count": len(seeds), "seeds": seeds,
        "opponents": args.opponents, "workers": args.workers,
        "min_cash": args.min_cash, "audit_mod": args.audit_mod,
        "screen_only": args.screen_only,
        "elapsed_seconds": perf_counter() - started,
        "overall": summarize(games),
        "by_opponent": {name: summarize(rows) for name, rows in by_opponent.items()},
        "games": sorted(games, key=lambda row: (row["seed"], row["opponent"], row["seat"])),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(result["overall"], flush=True)
    print(f"wrote {args.output}", flush=True)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Paired racing over daily milestone schedules around the current policy."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import random
from statistics import mean, stdev
from typing import Any

from production_fast_kaggriculture import run_fast_episode
from schedule_genome import (
    ScheduleGenome,
    anchor_schedules,
    configure_module,
    current_schedule,
    ev6_schedule,
    mutate,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OPPONENTS = ("public_v31", "public_v35", "public_v36", "public_v37")
_BASE_PATH = ""
_OPPONENT_PATHS: dict[str, str] = {}
_CANDIDATES: dict[str, Any] = {}
_OPPONENTS: dict[str, Any] = {}


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def worker_init(base_path: str, opponent_paths: dict[str, str]) -> None:
    global _BASE_PATH, _OPPONENT_PATHS, _CANDIDATES, _OPPONENTS
    _BASE_PATH = base_path
    _OPPONENT_PATHS = opponent_paths
    _CANDIDATES = {}
    _OPPONENTS = {}


def play(task: tuple[dict[str, Any], str, str, int, int]) -> dict[str, Any]:
    values, key, opponent, seed, seat = task
    try:
        candidate_agent = _CANDIDATES.get(key)
        if candidate_agent is None:
            module = load_module(
                Path(_BASE_PATH),
                f"schedule_candidate_{os.getpid()}_{abs(hash(key))}",
            )
            candidate_agent = configure_module(module, ScheduleGenome(**values))
            _CANDIDATES[key] = candidate_agent
        opponent_agent = _OPPONENTS.get(opponent)
        if opponent_agent is None:
            module = load_module(
                Path(_OPPONENT_PATHS[opponent]),
                f"schedule_opponent_{os.getpid()}_{opponent}",
            )
            opponent_agent = module.agent
            _OPPONENTS[opponent] = opponent_agent
        agents = (
            [candidate_agent, opponent_agent]
            if seat == 0
            else [opponent_agent, candidate_agent]
        )
        final = run_fast_episode(agents, seed=seed)
        reward = float(final[seat].reward)
        opponent_reward = float(final[1 - seat].reward)
        return {
            "key": key,
            "opponent": opponent,
            "seed": seed,
            "seat": seat,
            "reward": reward,
            "opponent_reward": opponent_reward,
            "margin": reward - opponent_reward,
            "win": reward > opponent_reward,
            "error": None,
        }
    except Exception as error:
        return {
            "key": key,
            "opponent": opponent,
            "seed": seed,
            "seat": seat,
            "reward": -1_000_000.0,
            "opponent_reward": 0.0,
            "margin": -1_000_000.0,
            "win": False,
            "error": repr(error),
        }


def row(genome: ScheduleGenome, label: str, parent: str = "") -> dict[str, Any]:
    return {"genome": genome.normalized(), "label": label, "parent": parent}


def unique(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for value in rows:
        result.setdefault(value["genome"].key(), value)
    return list(result.values())


def initial_pool(rng: random.Random, population: int) -> list[dict[str, Any]]:
    base = current_schedule()
    trace = ev6_schedule()
    rows = [row(base, "incumbent")]
    for index, genome in enumerate(anchor_schedules()):
        rows.append(row(genome, f"structural_anchor_{index}"))
    parents = anchor_schedules()
    attempts = 0
    while len(unique(rows)) < population and attempts < population * 100:
        attempts += 1
        parent = rng.choice(parents if rng.random() < 0.65 else [base, trace])
        changes = rng.choices((1, 2, 3, 4), weights=(4, 4, 2, 1))[0]
        genome = mutate(parent, rng, changes=changes)
        rows.append(row(genome, f"initial_mutation_{attempts}", parent.key()))
    return unique(rows)[:population]


def offspring_pool(
    summaries: list[dict[str, Any]],
    rng: random.Random,
    population: int,
) -> list[dict[str, Any]]:
    parents = [ScheduleGenome(**value["schedule"]) for value in summaries]
    rows = [row(current_schedule(), "incumbent")]
    rows.extend(
        row(parent, f"parent_{index}") for index, parent in enumerate(parents)
    )
    attempts = 0
    while len(unique(rows)) < population and attempts < population * 100:
        attempts += 1
        rank = min(int(rng.expovariate(0.75)), len(parents) - 1)
        parent = parents[rank]
        changes = rng.choices((1, 2, 3), weights=(5, 3, 1))[0]
        child = mutate(parent, rng, changes=changes)
        rows.append(row(child, f"offspring_{attempts}", parent.key()))
    return unique(rows)[:population]


def paired_summary(
    candidate: dict[str, Any],
    games: list[dict[str, Any]],
    baseline: dict[tuple[str, int, int], dict[str, Any]],
) -> dict[str, Any]:
    deltas: list[float] = []
    by_opponent: dict[str, dict[str, Any]] = {}
    for opponent in sorted({game["opponent"] for game in games}):
        subset = [game for game in games if game["opponent"] == opponent]
        opponent_deltas = [
            float(game["reward"])
            - float(baseline[(opponent, int(game["seed"]), int(game["seat"]))]["reward"])
            for game in subset
        ]
        deltas.extend(opponent_deltas)
        by_opponent[opponent] = {
            "games": len(subset),
            "mean_delta": mean(opponent_deltas),
            "mean_reward": mean(float(game["reward"]) for game in subset),
            "mean_margin": mean(float(game["margin"]) for game in subset),
            "win_rate": mean(float(bool(game["win"])) for game in subset),
            "errors": sum(game["error"] is not None for game in subset),
        }
    mean_delta = mean(deltas)
    stderr = stdev(deltas) / math.sqrt(len(deltas)) if len(deltas) > 1 else 0.0
    worst = min(value["mean_delta"] for value in by_opponent.values())
    errors = sum(game["error"] is not None for game in games)
    score = mean_delta - 0.5 * stderr + 0.25 * min(0.0, worst)
    if errors:
        score -= 1_000_000.0 * errors
    return {
        "key": candidate["genome"].key(),
        "label": candidate["label"],
        "parent": candidate["parent"],
        "schedule": candidate["genome"].to_dict(),
        "games": len(games),
        "mean_reward": mean(float(game["reward"]) for game in games),
        "mean_margin": mean(float(game["margin"]) for game in games),
        "win_rate": mean(float(bool(game["win"])) for game in games),
        "mean_delta": mean_delta,
        "stderr_delta": stderr,
        "lower_95_delta": mean_delta - 1.96 * stderr,
        "worst_opponent_delta": worst,
        "paired_score": score,
        "errors": errors,
        "by_opponent": by_opponent,
    }


def evaluate(
    pool: Any,
    candidates: list[dict[str, Any]],
    opponents: list[str],
    seeds: list[int],
) -> list[dict[str, Any]]:
    candidates = unique(candidates)
    baseline_key = current_schedule().key()
    if baseline_key not in {value["genome"].key() for value in candidates}:
        candidates.insert(0, row(current_schedule(), "incumbent"))
    tasks = [
        (value["genome"].to_dict(), value["genome"].key(), opponent, seed, seat)
        for value in candidates
        for opponent in opponents
        for seed in seeds
        for seat in (0, 1)
    ]
    by_key = {value["genome"].key(): [] for value in candidates}
    for game in pool.imap_unordered(play, tasks, chunksize=1):
        by_key[game["key"]].append(game)
    baseline_games = by_key[baseline_key]
    baseline = {
        (game["opponent"], int(game["seed"]), int(game["seat"])): game
        for game in baseline_games
    }
    summaries = [
        paired_summary(value, by_key[value["genome"].key()], baseline)
        for value in candidates
    ]
    summaries.sort(key=lambda value: value["paired_score"], reverse=True)
    return summaries


def seed_values(start: int, count: int) -> list[int]:
    return [start + index * 31 for index in range(count)]


def save_stage(
    output_dir: Path,
    name: str,
    seeds: list[int],
    results: list[dict[str, Any]],
) -> None:
    (output_dir / f"{name}.json").write_text(
        json.dumps({"seeds": seeds, "results": results}, indent=2) + "\n",
        encoding="utf-8",
    )
    best = results[0]
    print(
        f"{name}: {best['label']} delta={best['mean_delta']:+.1f} "
        f"lower95={best['lower_95_delta']:+.1f} "
        f"worst={best['worst_opponent_delta']:+.1f}",
        flush=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=ROOT / "main.py")
    parser.add_argument("--models-dir", type=Path, default=ROOT / "test")
    parser.add_argument("--opponents", nargs="*", default=list(DEFAULT_OPPONENTS))
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--population", type=int, default=64)
    parser.add_argument("--stage0-seeds", type=int, default=4)
    parser.add_argument("--stage1-seeds", type=int, default=16)
    parser.add_argument("--stage2-seeds", type=int, default=24)
    parser.add_argument("--final-seeds", type=int, default=100)
    parser.add_argument("--stage1-count", type=int, default=20)
    parser.add_argument("--elite-count", type=int, default=6)
    parser.add_argument("--finalists", type=int, default=3)
    parser.add_argument("--seed", type=int, default=20260801)
    parser.add_argument("--seed-start", type=int, default=13_100_000)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    opponents = {
        name: args.models_dir.resolve() / name / "main.py"
        for name in args.opponents
    }
    missing = [
        str(path) for path in (args.base.resolve(), *opponents.values())
        if not path.is_file()
    ]
    if missing:
        raise SystemExit("missing file(s): " + ", ".join(missing))
    metadata = {
        "method": "daily milestone schedule paired racing v1",
        "base": str(args.base.resolve()),
        "opponents": {name: str(path) for name, path in opponents.items()},
        "population": args.population,
        "stage0_seeds": args.stage0_seeds,
        "stage1_seeds": args.stage1_seeds,
        "stage2_seeds": args.stage2_seeds,
        "final_seeds": args.final_seeds,
        "random_seed": args.seed,
        "incumbent": current_schedule().to_dict(),
        "structural_anchors": [value.to_dict() for value in anchor_schedules()],
    }
    (output_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )

    rng = random.Random(args.seed)
    context = mp.get_context("spawn")
    workers = max(1, min(args.workers, os.cpu_count() or args.workers))
    with context.Pool(
        workers,
        initializer=worker_init,
        initargs=(
            str(args.base.resolve()),
            {name: str(path) for name, path in opponents.items()},
        ),
    ) as pool:
        stage0_seeds = seed_values(args.seed_start, args.stage0_seeds)
        stage0 = evaluate(
            pool, initial_pool(rng, args.population), list(opponents), stage0_seeds
        )
        save_stage(output_dir, "stage0_schedule", stage0_seeds, stage0)

        stage1_rows = [row(current_schedule(), "incumbent")]
        stage1_rows.extend(
            row(ScheduleGenome(**value["schedule"]), value["label"], value["parent"])
            for value in stage0
            if value["key"] != current_schedule().key()
        )
        stage1_seeds = seed_values(args.seed_start + 100_000, args.stage1_seeds)
        stage1 = evaluate(
            pool,
            stage1_rows[: args.stage1_count + 1],
            list(opponents),
            stage1_seeds,
        )
        save_stage(output_dir, "stage1_race", stage1_seeds, stage1)

        elites = [
            value for value in stage1 if value["key"] != current_schedule().key()
        ][: args.elite_count]
        stage2_rows = offspring_pool(elites, rng, args.population)
        stage2_seeds = seed_values(args.seed_start + 200_000, args.stage2_seeds)
        stage2 = evaluate(pool, stage2_rows, list(opponents), stage2_seeds)
        save_stage(output_dir, "stage2_offspring", stage2_seeds, stage2)

        final_rows = [row(current_schedule(), "incumbent")]
        final_rows.extend(
            row(ScheduleGenome(**value["schedule"]), value["label"], value["parent"])
            for value in stage2
            if value["key"] != current_schedule().key()
        )
        final_seeds = seed_values(args.seed_start + 300_000, args.final_seeds)
        final = evaluate(
            pool,
            final_rows[: args.finalists + 1],
            list(opponents),
            final_seeds,
        )
        save_stage(output_dir, "final_heldout", final_seeds, final)

    eligible = [
        value for value in final
        if value["key"] != current_schedule().key()
        and value["errors"] == 0
        and value["lower_95_delta"] > 0
        and value["worst_opponent_delta"] >= 0
    ]
    accepted = bool(eligible)
    selected = eligible[0] if eligible else next(
        value for value in final if value["key"] == current_schedule().key()
    )
    decision = {
        "accepted": accepted,
        "reason": (
            "positive held-out 95% lower bound and no opponent regression"
            if accepted else "held-out acceptance gate not met"
        ),
        "best_overall": final[0],
        "selected": selected,
    }
    (output_dir / "decision.json").write_text(
        json.dumps(decision, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "best_schedule.json").write_text(
        json.dumps(selected["schedule"], indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"decision accepted={accepted} selected={selected['label']} "
        f"delta={selected['mean_delta']:+.1f}",
        flush=True,
    )


if __name__ == "__main__":
    main()

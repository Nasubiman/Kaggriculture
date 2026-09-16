#!/usr/bin/env python3
"""Paired multi-opponent search for the architecture-independent genome."""

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

from current_genome import CurrentGenome, anchor_genomes, configure_module, crossover, mutate
from production_fast_kaggriculture import run_fast_episode
from agent_runtime import optimize_agent_module
from reference_runtime import optimize_reference_agent_module


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OPPONENTS = (
    "public_v45_competitive_20260916",
    "public_v43_competitive_20260915",
    "public_v41_competitive_20260914",
    "public_v38_low_pressure_20260914",
    "results5_20260913",
)
_BASE = ""
_OPPONENT_PATHS: dict[str, str] = {}
_AGENTS: dict[str, Any] = {}
_OPPONENTS: dict[str, Any] = {}

# Permit only an immaterial per-opponent reward trade-off.  Episode rewards are
# about 100k, so an absolute zero-tolerance gate overreacts to tiny changes.
MAX_OPPONENT_RELATIVE_REWARD_REGRESSION = 0.002


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return optimize_agent_module(module)


def load_reference_module(path: Path, name: str, model_name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return optimize_reference_agent_module(module, model_name)


def read_incumbent(path: Path) -> CurrentGenome:
    module = load_module(path, "current_genome_incumbent_probe")
    values = getattr(module, "_FROZEN_CURRENT_GENOME", None)
    if isinstance(values, dict):
        fields = CurrentGenome.__dataclass_fields__
        return CurrentGenome(**{k: v for k, v in values.items() if k in fields}).normalized()
    return CurrentGenome()


def worker_init(base: str, opponents: dict[str, str]):
    global _BASE, _OPPONENT_PATHS, _AGENTS, _OPPONENTS
    _BASE, _OPPONENT_PATHS = base, opponents
    _AGENTS, _OPPONENTS = {}, {}


def play(task: tuple[dict[str, Any], str, str, int, int]):
    values, key, opponent, seed, seat = task
    try:
        candidate = _AGENTS.get(key)
        if candidate is None:
            module = load_module(Path(_BASE), f"cg_{os.getpid()}_{abs(hash(key))}")
            candidate = configure_module(module, CurrentGenome(**values))
            _AGENTS[key] = candidate
        rival = _OPPONENTS.get(opponent)
        if rival is None:
            rival = load_reference_module(
                Path(_OPPONENT_PATHS[opponent]),
                f"cgo_{os.getpid()}_{opponent}",
                opponent,
            ).agent
            _OPPONENTS[opponent] = rival
        agents = [candidate, rival] if seat == 0 else [rival, candidate]
        final = run_fast_episode(agents, seed=seed)
        reward = float(final[seat].reward)
        rival_reward = float(final[1 - seat].reward)
        return dict(key=key, opponent=opponent, seed=seed, seat=seat,
                    reward=reward, opponent_reward=rival_reward,
                    margin=reward-rival_reward, win=reward > rival_reward, error=None)
    except Exception as error:
        return dict(key=key, opponent=opponent, seed=seed, seat=seat,
                    reward=-1_000_000.0, opponent_reward=0.0,
                    margin=-1_000_000.0, win=False, error=repr(error))


def play_batch(task: tuple[dict[str, Any], str, str, list[int]]):
    """Keep one candidate/opponent pair hot for all seeds and both seats."""
    values, key, opponent, seeds = task
    return [
        play((values, key, opponent, seed, seat))
        for seed in seeds for seat in (0, 1)
    ]


def row(genome: CurrentGenome, label: str, parent: str | None = None):
    return {"genome": genome.normalized(), "label": label, "parent": parent}


def unique(rows):
    by_key = {}
    for value in rows:
        by_key.setdefault(value["genome"].key(), value)
    return list(by_key.values())


def diverse_results(results, count: int, base_key: str):
    """Retain the Pareto frontier instead of collapsing to one scalar objective."""
    candidates = [value for value in results
                  if value["key"] != base_key and value["errors"] == 0]
    metrics = ("mean_delta", "mean_margin_delta",
               "worst_opponent_delta", "worst_opponent_margin_delta")
    frontier = []
    for candidate in candidates:
        dominated = any(
            all(other[name] >= candidate[name] for name in metrics)
            and any(other[name] > candidate[name] for name in metrics)
            for other in candidates if other["key"] != candidate["key"]
        )
        if not dominated:
            frontier.append(candidate)
    strict = [value for value in candidates
              if value["lower_95_delta"] > 0
              and value["worst_opponent_relative_delta"]
                  >= -MAX_OPPONENT_RELATIVE_REWARD_REGRESSION
              and value["mean_margin_delta"] >= 0
              and value["worst_opponent_margin_delta"] >= 0]
    positive_both = [value for value in candidates
                     if value["mean_delta"] > 0 and value["mean_margin_delta"] > 0]
    ordered = strict + sorted(frontier, key=lambda value: value["paired_score"], reverse=True)
    ordered += positive_both + candidates
    selected, seen = [], set()
    for value in ordered:
        if value["key"] in seen:
            continue
        selected.append(value); seen.add(value["key"])
        if len(selected) >= count:
            break
    return selected


def initial_pool(base: CurrentGenome, rng: random.Random, population: int):
    neighborhood = unique([
        row(value, f"incumbent_anchor_{index}")
        for index, value in enumerate(anchor_genomes(base))
    ])
    anchor_budget = min(len(neighborhood), max(1, population // 2))
    anchor_indices = (
        [0] if anchor_budget == 1 else [
            round(index * (len(neighborhood) - 1) / (anchor_budget - 1))
            for index in range(anchor_budget)
        ]
    )
    rows = [row(base, "incumbent"), *(
        neighborhood[index] for index in anchor_indices[1:]
    )]
    attempts = 0
    while len(unique(rows)) < population and attempts < population * 100:
        attempts += 1
        parent = base if rng.random() < 0.7 else rng.choice(neighborhood)["genome"]
        if rng.random() < 0.25:
            parent = crossover(parent, rng.choice(neighborhood)["genome"], rng)
        child = mutate(parent, rng, rng.choices((1, 2, 3), (5, 3, 1))[0])
        rows.append(row(child, f"incumbent_mutation_{attempts}", parent.key()))
    return unique(rows)[:population]


def offspring(base: CurrentGenome, ranked, rng: random.Random, population: int):
    parents = [CurrentGenome(**value["genome"]) for value in ranked] or [base]
    rows = [row(base, "incumbent")]
    rows += [row(value, f"elite_{index}") for index, value in enumerate(parents)]
    attempts = 0
    while len(unique(rows)) < population and attempts < population * 100:
        attempts += 1
        parent = parents[min(int(rng.expovariate(0.8)), len(parents)-1)]
        child = mutate(parent, rng, rng.choices((1, 2, 3), (6, 3, 1))[0])
        if len(parents) > 1 and rng.random() < 0.30:
            child = crossover(child, rng.choice(parents), rng)
        rows.append(row(child, f"offspring_{attempts}", parent.key()))
    return unique(rows)[:population]


def summarize(candidate, games, baseline):
    deltas, margin_deltas, by_opponent = [], [], {}
    for opponent in sorted({game["opponent"] for game in games}):
        subset = [game for game in games if game["opponent"] == opponent]
        values = [
            game["reward"] - baseline[(opponent, game["seed"], game["seat"])]["reward"]
            for game in subset
        ]
        opponent_margin_deltas = [
            game["margin"] - baseline[(opponent, game["seed"], game["seat"])]["margin"]
            for game in subset
        ]
        baseline_rewards = [
            baseline[(opponent, game["seed"], game["seat"])]["reward"]
            for game in subset
        ]
        baseline_mean_reward = mean(baseline_rewards)
        deltas += values
        margin_deltas += opponent_margin_deltas
        by_opponent[opponent] = {
            "games": len(subset), "mean_delta": mean(values),
            "relative_delta": mean(values) / max(1.0, abs(baseline_mean_reward)),
            "mean_margin_delta": mean(opponent_margin_deltas),
            "mean_reward": mean(game["reward"] for game in subset),
            "baseline_mean_reward": baseline_mean_reward,
            "mean_margin": mean(game["margin"] for game in subset),
            "win_rate": mean(float(game["win"]) for game in subset),
            "errors": sum(game["error"] is not None for game in subset),
        }
    stderr = stdev(deltas) / math.sqrt(len(deltas)) if len(deltas) > 1 else 0.0
    worst = min(value["mean_delta"] for value in by_opponent.values())
    worst_relative = min(value["relative_delta"] for value in by_opponent.values())
    worst_margin = min(value["mean_margin_delta"] for value in by_opponent.values())
    errors = sum(game["error"] is not None for game in games)
    paired_score = (mean(deltas) - 0.5 * stderr + 0.50 * mean(margin_deltas)
                    + 0.35 * min(0.0, worst) + 0.25 * min(0.0, worst_margin))
    if errors:
        paired_score -= 1_000_000 * errors
    return {
        "key": candidate["genome"].key(), "label": candidate["label"],
        "parent": candidate["parent"], "genome": candidate["genome"].to_dict(),
        "games": len(games), "mean_reward": mean(g["reward"] for g in games),
        "mean_margin": mean(g["margin"] for g in games),
        "win_rate": mean(float(g["win"]) for g in games),
        "mean_delta": mean(deltas), "stderr_delta": stderr,
        "mean_margin_delta": mean(margin_deltas),
        "lower_95_delta": mean(deltas) - 1.96 * stderr,
        "worst_opponent_delta": worst, "paired_score": paired_score,
        "worst_opponent_relative_delta": worst_relative,
        "worst_opponent_margin_delta": worst_margin,
        "errors": errors, "by_opponent": by_opponent,
    }


def evaluate(pool, candidates, opponents, seeds, baseline_genome, *, batched=True):
    candidates = unique(candidates)
    baseline_key = baseline_genome.key()
    if baseline_key not in {value["genome"].key() for value in candidates}:
        candidates.insert(0, row(baseline_genome, "incumbent"))
    games = {value["genome"].key(): [] for value in candidates}
    if batched:
        tasks = [
            (value["genome"].to_dict(), value["genome"].key(), opponent, seeds)
            for value in candidates for opponent in opponents
        ]
        batches = pool.imap_unordered(play_batch, tasks, chunksize=1)
    else:
        scalar_tasks = [
            (value["genome"].to_dict(), value["genome"].key(), opponent, seed, seat)
            for value in candidates for opponent in opponents
            for seed in seeds for seat in (0, 1)
        ]
        batches = ([game] for game in pool.imap_unordered(
            play, scalar_tasks, chunksize=1
        ))
    for batch in batches:
        for game in batch:
            games[game["key"]].append(game)
    baseline = {
        (g["opponent"], g["seed"], g["seat"]): g for g in games[baseline_key]
    }
    results = [summarize(value, games[value["genome"].key()], baseline) for value in candidates]
    results.sort(key=lambda value: value["paired_score"], reverse=True)
    return results


def save(path: Path, seeds, results):
    path.write_text(json.dumps({"seeds": seeds, "results": results}, indent=2)+"\n")
    best = results[0]
    print(f"{path.stem}: {best['label']} delta={best['mean_delta']:+.1f} "
          f"lower95={best['lower_95_delta']:+.1f} worst={best['worst_opponent_delta']:+.1f} "
          f"margin_delta={best['mean_margin_delta']:+.1f} "
          f"worst_margin={best['worst_opponent_margin_delta']:+.1f}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=ROOT / "main.py")
    parser.add_argument("--models-dir", type=Path, default=ROOT / "test")
    parser.add_argument("--opponents", nargs="*", default=list(DEFAULT_OPPONENTS))
    parser.add_argument("--workers", type=int, default=24)
    parser.add_argument("--population", type=int, default=48)
    parser.add_argument("--screen-seeds", type=int, default=8)
    parser.add_argument("--race-seeds", type=int, default=24)
    parser.add_argument("--final-seeds", type=int, default=200)
    parser.add_argument("--race-count", type=int, default=16)
    parser.add_argument("--elite-count", type=int, default=6)
    parser.add_argument("--finalists", type=int, default=4)
    parser.add_argument("--task-mode", choices=("batch", "game"), default="batch")
    parser.add_argument("--seed", type=int, default=20260913)
    parser.add_argument("--seed-start", type=int, default=19_130_000)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve(); output.mkdir(parents=True, exist_ok=True)
    paths = {name: args.models_dir / name / "main.py" for name in args.opponents}
    missing = [str(path) for path in (args.base, *paths.values()) if not path.is_file()]
    if missing: raise SystemExit("missing file(s): " + ", ".join(missing))
    base = read_incumbent(args.base.resolve())
    rng = random.Random(args.seed)
    metadata = {"method": "incumbent-centered paired multi-opponent genome v3",
                "base": str(args.base.resolve()), "opponents": args.opponents,
                "incumbent": base.to_dict(), "anchors": [g.to_dict() for g in anchor_genomes(base)]}
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2)+"\n")
    context = mp.get_context("spawn")
    workers = max(1, min(args.workers, os.cpu_count() or args.workers))
    with context.Pool(workers, initializer=worker_init,
                      initargs=(str(args.base.resolve()), {k: str(v.resolve()) for k,v in paths.items()})) as pool:
        seeds0 = [args.seed_start + 31*i for i in range(args.screen_seeds)]
        stage0 = evaluate(pool, initial_pool(base, rng, args.population), args.opponents,
                          seeds0, base, batched=args.task_mode == "batch")
        save(output / "stage0_screen.json", seeds0, stage0)
        race_rows = [row(base, "incumbent")] + [
            row(CurrentGenome(**v["genome"]), v["label"], v["parent"])
            for v in diverse_results(stage0, args.race_count, base.key())
        ]
        seeds1 = [args.seed_start + 100_000 + 31*i for i in range(args.race_seeds)]
        stage1 = evaluate(pool, race_rows, args.opponents, seeds1, base,
                          batched=args.task_mode == "batch")
        save(output / "stage1_race.json", seeds1, stage1)
        elite = diverse_results(stage1, args.elite_count, base.key())
        stage2 = evaluate(pool, offspring(base, elite, rng, args.population),
                          args.opponents, seeds1, base,
                          batched=args.task_mode == "batch")
        save(output / "stage2_offspring.json", seeds1, stage2)
        final_rows = [row(base, "incumbent")] + [
            row(CurrentGenome(**v["genome"]), v["label"], v["parent"])
            for v in diverse_results(stage2, args.finalists, base.key())
        ]
        seeds2 = [args.seed_start + 200_000 + 31*i for i in range(args.final_seeds)]
        final = evaluate(pool, final_rows, args.opponents, seeds2, base,
                         batched=args.task_mode == "batch")
        save(output / "final_heldout.json", seeds2, final)
    eligible = [v for v in final if v["key"] != base.key() and v["errors"] == 0
                and v["lower_95_delta"] > 0
                and v["worst_opponent_relative_delta"]
                    >= -MAX_OPPONENT_RELATIVE_REWARD_REGRESSION
                and v["mean_margin_delta"] >= 0
                and v["worst_opponent_margin_delta"] >= 0]
    accepted = bool(eligible)
    selected = eligible[0] if eligible else next(v for v in final if v["key"] == base.key())
    decision = {"accepted": accepted,
                "reason": ("positive reward lower bound, <=0.2% per-opponent reward "
                           "regression, and no margin regression" if accepted
                           else "held-out reward/margin gate not met"),
                "best_overall": final[0], "selected": selected}
    (output / "decision.json").write_text(json.dumps(decision, indent=2)+"\n")
    (output / "best_genome.json").write_text(json.dumps(selected["genome"], indent=2)+"\n")
    print(f"decision accepted={accepted} selected={selected['label']} delta={selected['mean_delta']:+.1f}")


if __name__ == "__main__":
    main()

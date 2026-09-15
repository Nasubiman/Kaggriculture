#!/usr/bin/env python3
"""Block-structured, absolute-reward search around the 0801_ev2 engine.

The expensive simulation budget is spent only after the engine families have
been screened.  All candidates use common random numbers, play both seats, and
face a fixed league containing ev1/ev2/ev3 and the current incumbent.  Search
is local and block-aware; crossovers never combine incompatible policy engines.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import random
from statistics import mean
import time
from typing import Any

from ev2_genome import (
    Ev2Genome,
    GENE_BLOCKS,
    configure_module,
    crossover,
    family_seed_genomes,
    mutate,
)
from production_fast_kaggriculture import run_fast_episode


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OPPONENTS = (
    "0801_ev1",
    "0801_ev2",
    "0801_ev3",
    "0801_v1",
    "0801_ev4",
    "0801_ev5",
)
_ENGINE_PATH = ""
_OPPONENT_PATHS: dict[str, str] = {}
_FAST_RUNNER = True


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def worker_init(engine: str, opponents: dict[str, str], fast_runner: bool) -> None:
    global _ENGINE_PATH, _OPPONENT_PATHS, _FAST_RUNNER
    _ENGINE_PATH = engine
    _OPPONENT_PATHS = opponents
    _FAST_RUNNER = fast_runner


def play_task(task: tuple[dict[str, Any], str, str, int, int]) -> dict[str, Any]:
    values, key, opponent_name, seed, seat = task
    suffix = f"{os.getpid()}_{opponent_name}_{seed}_{seat}_{abs(hash(key))}"
    try:
        candidate_module = load_module(
            Path(_ENGINE_PATH), f"ev2_candidate_{suffix}"
        )
        candidate = configure_module(candidate_module, Ev2Genome(**values))
        opponent_module = load_module(
            Path(_OPPONENT_PATHS[opponent_name]), f"ev2_opponent_{suffix}"
        )
        opponent = opponent_module.agent
        agents = [candidate, opponent] if seat == 0 else [opponent, candidate]
        if _FAST_RUNNER:
            final = run_fast_episode(agents, seed=seed)
        else:
            from kaggle_environments import make

            environment = make(
                "kaggriculture",
                configuration={"episodeSteps": 720, "seed": seed},
                debug=False,
            )
            environment.run(agents)
            final = environment.steps[-1]
        reward = float(final[seat].reward)
        opponent_reward = float(final[1 - seat].reward)
        return {
            "key": key,
            "opponent": opponent_name,
            "seed": seed,
            "seat": seat,
            "reward": reward,
            "opponent_reward": opponent_reward,
            "margin": reward - opponent_reward,
            "win": reward > opponent_reward,
            "tie": reward == opponent_reward,
            "status": str(final[seat].status),
            "error": None,
        }
    except Exception as error:
        return {
            "key": key,
            "opponent": opponent_name,
            "seed": seed,
            "seat": seat,
            "reward": -1_000_000.0,
            "opponent_reward": 0.0,
            "margin": -1_000_000.0,
            "win": False,
            "tie": False,
            "status": "ERROR",
            "error": repr(error),
        }


def summarize(genome: Ev2Genome, games: list[dict[str, Any]]) -> dict[str, Any]:
    by_opponent = {}
    for opponent in sorted({game["opponent"] for game in games}):
        subset = [game for game in games if game["opponent"] == opponent]
        by_opponent[opponent] = {
            "games": len(subset),
            "mean_reward": mean(float(game["reward"]) for game in subset),
            "mean_margin": mean(float(game["margin"]) for game in subset),
            "win_rate": mean(float(bool(game["win"])) for game in subset),
            "errors": sum(game["error"] is not None for game in subset),
        }
    macro_reward = mean(value["mean_reward"] for value in by_opponent.values())
    worst_reward = min(value["mean_reward"] for value in by_opponent.values())
    mean_margin = mean(float(game["margin"]) for game in games)
    errors = sum(game["error"] is not None for game in games)
    # Absolute reward is 95% of the score.  Margin is only a safety tie-breaker.
    objective = 0.75 * macro_reward + 0.25 * worst_reward + 0.05 * mean_margin
    if errors:
        objective -= 1_000_000.0 * errors
    return {
        "key": genome.key(),
        "genome": genome.to_dict(),
        "objective": objective,
        "games": len(games),
        "mean_reward": macro_reward,
        "worst_opponent_reward": worst_reward,
        "mean_margin": mean_margin,
        "win_rate": mean(float(bool(game["win"])) for game in games),
        "errors": errors,
        "by_opponent": by_opponent,
    }


def evaluate(
    pool: Any,
    genomes: list[Ev2Genome],
    opponents: list[str],
    seeds: list[int],
) -> list[dict[str, Any]]:
    unique = {genome.key(): genome.normalized() for genome in genomes}
    tasks = [
        (genome.to_dict(), key, opponent, seed, seat)
        for key, genome in unique.items()
        for opponent in opponents
        for seed in seeds
        for seat in (0, 1)
    ]
    games: dict[str, list[dict[str, Any]]] = {key: [] for key in unique}
    for game in pool.imap_unordered(play_task, tasks, chunksize=1):
        games[game["key"]].append(game)
    return [summarize(genome, games[key]) for key, genome in unique.items()]


def proposal_pool(
    elites: list[Ev2Genome], baseline: Ev2Genome, size: int, rng: random.Random
) -> list[Ev2Genome]:
    parents = elites or [baseline]
    candidates = [baseline, *parents[:6], *family_seed_genomes(parents[0])]

    # Systematic one-block probes ensure every economic subsystem is explored.
    for parent in parents[:3]:
        for block in GENE_BLOCKS:
            candidates.append(mutate(parent, rng, block=block, changes=1))
            candidates.append(mutate(parent, rng, block=block, changes=2))

    seen = set()
    unique = []
    for genome in candidates:
        if genome.key() not in seen:
            seen.add(genome.key())
            unique.append(genome.normalized())

    attempts = 0
    while len(unique) < size and attempts < size * 100:
        attempts += 1
        rank = min(int(rng.expovariate(0.9)), len(parents) - 1)
        parent = parents[rank]
        if len(parents) > 1 and rng.random() < 0.18:
            other = rng.choice(parents)
            child = mutate(crossover(parent, other, rng), rng)
        else:
            child = mutate(parent, rng)
            if rng.random() < 0.25:
                child = mutate(child, rng)
        if child.key() not in seen:
            seen.add(child.key())
            unique.append(child)
    return unique


def merge_record(
    archive: dict[str, dict[str, Any]], record: dict[str, Any]
) -> None:
    previous = archive.get(record["key"])
    if previous is None or record["games"] >= previous["games"]:
        archive[record["key"]] = record


def save_state(
    output_dir: Path,
    generation: int,
    elapsed: float,
    archive: dict[str, dict[str, Any]],
    history: list[dict[str, Any]],
) -> None:
    ranked = sorted(archive.values(), key=lambda row: row["objective"], reverse=True)
    payload = {
        "generation": generation,
        "elapsed_seconds": elapsed,
        "metric": (
            "0.75*league_mean_reward + 0.25*worst_opponent_reward "
            "+ 0.05*mean_margin"
        ),
        "best": ranked[0] if ranked else None,
        "top": ranked[:25],
        "history": history,
    }
    temporary = output_dir / "search_state.json.tmp"
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output_dir / "search_state.json")
    if ranked:
        (output_dir / "best_genome.json").write_text(
            json.dumps(ranked[0]["genome"], indent=2) + "\n", encoding="utf-8"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--minutes", type=float, default=5.0)
    parser.add_argument("--population", type=int, default=32)
    parser.add_argument("--stage1", type=int, default=10)
    parser.add_argument("--stage2", type=int, default=3)
    parser.add_argument("--stage0-seeds", type=int, default=1)
    parser.add_argument("--stage1-seeds", type=int, default=3)
    parser.add_argument("--anchor-seeds", type=int, default=4)
    parser.add_argument("--validation-seeds", type=int, default=8)
    parser.add_argument("--workers", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20260801)
    parser.add_argument(
        "--engine", type=Path, default=ROOT / "test/0801_ev2/main.py"
    )
    parser.add_argument("--incumbent-genome", type=Path)
    parser.add_argument("--models-dir", type=Path, default=ROOT / "test")
    parser.add_argument("--opponents", nargs="*", default=list(DEFAULT_OPPONENTS))
    parser.add_argument(
        "--fast-runner", action=argparse.BooleanOptionalAction, default=True
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    engine = args.engine.resolve()
    models_dir = args.models_dir.resolve()
    opponent_paths = {
        name: (models_dir / name / "main.py").resolve() for name in args.opponents
    }
    missing = [str(path) for path in [engine, *opponent_paths.values()] if not path.is_file()]
    if missing:
        raise SystemExit("missing policy file(s): " + ", ".join(missing))

    workers = max(1, min(args.workers, os.cpu_count() or args.workers))
    rng = random.Random(args.seed)
    started = time.monotonic()
    deadline = started + max(0.05, args.minutes) * 60.0
    validation_seeds = [8_810_000 + index * 37 for index in range(args.validation_seeds)]
    incumbent = Ev2Genome()
    if args.incumbent_genome:
        raw = json.loads(args.incumbent_genome.read_text(encoding="utf-8"))
        fields = Ev2Genome.__dataclass_fields__
        incumbent = Ev2Genome(
            **{name: value for name, value in raw.items() if name in fields}
        ).normalized()
    archive: dict[str, dict[str, Any]] = {}
    history: list[dict[str, Any]] = []
    generation = 0

    metadata = {
        "engine": str(engine),
        "opponents": {name: str(path) for name, path in opponent_paths.items()},
        "minutes": args.minutes,
        "population": args.population,
        "workers": workers,
        "seed": args.seed,
        "fast_runner": args.fast_runner,
        "search_space": "ev2 block-local hierarchical v1",
        "blocks": {name: list(fields) for name, fields in GENE_BLOCKS.items()},
        "baseline": incumbent.to_dict(),
        "family_anchors": [
            genome.to_dict() for genome in family_seed_genomes(incumbent)
        ],
    }
    (output_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )

    context = mp.get_context("spawn")
    with context.Pool(
        workers,
        initializer=worker_init,
        initargs=(
            str(engine),
            {name: str(path) for name, path in opponent_paths.items()},
            args.fast_runner,
        ),
    ) as pool:
        anchors = evaluate(
            pool,
            family_seed_genomes(incumbent),
            list(opponent_paths),
            validation_seeds[: max(1, min(args.anchor_seeds, len(validation_seeds)))],
        )
        for record in anchors:
            merge_record(archive, record)
        elites = [
            Ev2Genome(**record["genome"])
            for record in sorted(anchors, key=lambda row: row["objective"], reverse=True)
        ]
        save_state(output_dir, generation, time.monotonic() - started, archive, history)

        while time.monotonic() < deadline:
            proposals = proposal_pool(elites, incumbent, args.population, rng)
            base_seed = 1_810_000 + generation * 10_000
            stage0_seeds = [base_seed + index * 17 for index in range(args.stage0_seeds)]
            stage0 = evaluate(
                pool, proposals, list(opponent_paths), stage0_seeds
            )
            stage0.sort(key=lambda row: row["objective"], reverse=True)

            stage1_genomes = [
                Ev2Genome(**row["genome"])
                for row in stage0[: max(1, min(args.stage1, len(stage0)))]
            ]
            stage1_seeds = [
                base_seed + 1_000 + index * 29 for index in range(args.stage1_seeds)
            ]
            stage1 = evaluate(
                pool, stage1_genomes, list(opponent_paths), stage1_seeds
            )
            stage1.sort(key=lambda row: row["objective"], reverse=True)

            finalists = [
                Ev2Genome(**row["genome"])
                for row in stage1[: max(1, min(args.stage2, len(stage1)))]
            ]
            # Re-evaluate the incumbent on the same held-out seeds each generation.
            finalists.extend(elites[:2])
            validation = evaluate(
                pool, finalists, list(opponent_paths), validation_seeds
            )
            for record in validation:
                merge_record(archive, record)
            ranked = sorted(
                archive.values(), key=lambda row: row["objective"], reverse=True
            )
            elites = [Ev2Genome(**record["genome"]) for record in ranked[:12]]
            history.append(
                {
                    "generation": generation,
                    "elapsed_seconds": time.monotonic() - started,
                    "stage0_best": stage0[0],
                    "stage1_best": stage1[0],
                    "validated_best": ranked[0],
                }
            )
            save_state(
                output_dir,
                generation,
                time.monotonic() - started,
                archive,
                history,
            )
            print(
                f"generation={generation} elapsed={time.monotonic() - started:.1f}s "
                f"reward={ranked[0]['mean_reward']:.1f} "
                f"worst={ranked[0]['worst_opponent_reward']:.1f} "
                f"objective={ranked[0]['objective']:.1f}",
                flush=True,
            )
            generation += 1

    ranked = sorted(archive.values(), key=lambda row: row["objective"], reverse=True)
    best = ranked[0]
    print(
        f"done generations={generation} reward={best['mean_reward']:.1f} "
        f"worst={best['worst_opponent_reward']:.1f} objective={best['objective']:.1f}"
    )
    print(f"wrote {output_dir / 'best_genome.json'}")


if __name__ == "__main__":
    main()

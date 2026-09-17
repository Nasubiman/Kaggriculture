#!/usr/bin/env python3
"""Search the current genome for paired win-rate gains against new rivals."""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
from pathlib import Path
import random
from statistics import mean

from current_genome import CurrentGenome
from search_current_genomes import (
    evaluate, initial_pool, offspring, read_incumbent, row, worker_init,
)


def rank(results: list[dict], targets: list[str], guards: list[str],
         base_key: str) -> list[dict]:
    incumbent = next(result for result in results if result["key"] == base_key)
    baseline = incumbent["by_opponent"]
    for result in results:
        by_name = result["by_opponent"]
        gains = [by_name[name]["win_rate"] - baseline[name]["win_rate"]
                 for name in targets]
        guard_losses = [baseline[name]["win_rate"] - by_name[name]["win_rate"]
                        for name in guards]
        # A candidate must help the *weakest* target, not merely win extra
        # games against an opponent already beaten comfortably.
        result["target_win_gains"] = dict(zip(targets, gains))
        result["guard_win_losses"] = dict(zip(guards, guard_losses))
        result["win_objective"] = (
            1000.0 * min(gains) + 250.0 * mean(gains)
            - 1500.0 * max(0.0, max(guard_losses, default=0.0) - 0.01)
            + 0.025 * result["mean_margin_delta"]
            + 0.002 * result["mean_delta"]
            - 1_000_000.0 * result["errors"]
        )
    return sorted(results, key=lambda result: result["win_objective"],
                  reverse=True)


def save(path: Path, seeds: list[int], results: list[dict]) -> None:
    path.write_text(json.dumps({"seeds": seeds, "results": results}, indent=2)
                    + "\n", encoding="utf-8")
    best = results[0]
    print(f"{path.stem}: {best['label']} objective={best['win_objective']:+.1f} "
          f"target_gains={best['target_win_gains']} "
          f"guard_losses={best['guard_win_losses']}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=Path("main.py"))
    parser.add_argument("--models-dir", type=Path, default=Path("test"))
    parser.add_argument("--targets", nargs="+", required=True)
    parser.add_argument("--guards", nargs="+", required=True)
    parser.add_argument("--workers", type=int, default=20)
    parser.add_argument("--population", type=int, default=48)
    parser.add_argument("--screen-seeds", type=int, default=8)
    parser.add_argument("--race-seeds", type=int, default=24)
    parser.add_argument("--final-seeds", type=int, default=100)
    parser.add_argument("--race-count", type=int, default=12)
    parser.add_argument("--elite-count", type=int, default=5)
    parser.add_argument("--finalists", type=int, default=4)
    parser.add_argument("--seed", type=int, default=20260917)
    parser.add_argument("--seed-start", type=int, default=41_000_000)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    opponents = list(dict.fromkeys([*args.targets, *args.guards]))
    paths = {name: (args.models_dir / name / "main.py").resolve()
             for name in opponents}
    missing = [str(path) for path in (args.base, *paths.values())
               if not path.is_file()]
    if missing:
        raise SystemExit("missing file(s): " + ", ".join(missing))
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    base = read_incumbent(args.base.resolve())
    rng = random.Random(args.seed)
    (output / "metadata.json").write_text(json.dumps({
        "method": "paired win-rate genome search",
        "base": str(args.base.resolve()), "targets": args.targets,
        "guards": args.guards, "optimize_runtime": False,
        "incumbent": base.to_dict(),
    }, indent=2) + "\n", encoding="utf-8")

    workers = max(1, min(args.workers, os.cpu_count() or args.workers))
    with mp.get_context("spawn").Pool(
        workers, initializer=worker_init,
        initargs=(str(args.base.resolve()),
                  {name: str(path) for name, path in paths.items()}, False),
    ) as pool:
        def assess(candidates, seeds):
            return rank(evaluate(pool, candidates, opponents, seeds, base),
                        args.targets, args.guards, base.key())

        screen_seeds = [args.seed_start + 31 * i
                        for i in range(args.screen_seeds)]
        screen = assess(initial_pool(base, rng, args.population), screen_seeds)
        save(output / "screen.json", screen_seeds, screen)

        race_candidates = [row(base, "incumbent")] + [
            row(CurrentGenome(**result["genome"]), result["label"],
                result["parent"])
            for result in screen if result["key"] != base.key()
        ][:args.race_count]
        race_seeds = [args.seed_start + 100_000 + 31 * i
                      for i in range(args.race_seeds)]
        race = assess(race_candidates, race_seeds)
        save(output / "race.json", race_seeds, race)

        elite = [result for result in race if result["key"] != base.key()]
        offspring_candidates = offspring(base, elite[:args.elite_count], rng,
                                         args.population)
        offspring_results = assess(offspring_candidates, race_seeds)
        save(output / "offspring.json", race_seeds, offspring_results)

        final_candidates = [row(base, "incumbent")] + [
            row(CurrentGenome(**result["genome"]), result["label"],
                result["parent"])
            for result in offspring_results if result["key"] != base.key()
        ][:args.finalists]
        final_seeds = [args.seed_start + 200_000 + 31 * i
                       for i in range(args.final_seeds)]
        final = assess(final_candidates, final_seeds)
        save(output / "final_heldout.json", final_seeds, final)

    incumbent = next(result for result in final if result["key"] == base.key())
    eligible = [result for result in final if result["key"] != base.key()
                and result["errors"] == 0
                and min(result["target_win_gains"].values()) >= 0
                and mean(result["target_win_gains"].values()) >= 0.02
                and max(result["guard_win_losses"].values()) <= 0.01
                and all(result["by_opponent"][name]["relative_delta"] >= -0.01
                        for name in args.guards)]
    selected = eligible[0] if eligible else incumbent
    (output / "decision.json").write_text(json.dumps({
        "accepted": bool(eligible), "selected": selected,
        "reason": ("target win gain without guard regression" if eligible
                   else "no candidate met the held-out win/guard gate"),
    }, indent=2) + "\n", encoding="utf-8")
    (output / "best_genome.json").write_text(
        json.dumps(selected["genome"], indent=2) + "\n", encoding="utf-8")
    print(f"decision accepted={bool(eligible)} selected={selected['label']} "
          f"target_gains={selected['target_win_gains']}", flush=True)


if __name__ == "__main__":
    main()

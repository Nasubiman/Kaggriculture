#!/usr/bin/env python3
"""Paired-delta coordinate and pairwise search around the incumbent genome."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import multiprocessing as mp
import os
from dataclasses import asdict, replace
from pathlib import Path
from statistics import mean, stdev
from typing import Any

from ev2_genome import Ev2Genome, FIELD_STEPS, GENE_BLOCKS, configure_module
from production_fast_kaggriculture import run_fast_episode


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OPPONENTS = ("public_v31", "public_v35", "public_v36", "public_v37")
_ENGINE_PATH = ""
_OPPONENT_PATHS: dict[str, str] = {}
_CANDIDATE_AGENTS: dict[str, Any] = {}
_OPPONENT_AGENTS: dict[str, Any] = {}


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def incumbent_genome(path: Path) -> Ev2Genome:
    module = load_module(path, "paired_coordinate_incumbent")
    raw = getattr(module, "_FROZEN_EV2_GENOME", None)
    if not isinstance(raw, dict):
        raise RuntimeError(f"{path} has no _FROZEN_EV2_GENOME")
    fields = Ev2Genome.__dataclass_fields__
    return Ev2Genome(
        **{name: value for name, value in raw.items() if name in fields}
    ).normalized()


def worker_init(engine_path: str, opponent_paths: dict[str, str]) -> None:
    global _ENGINE_PATH, _OPPONENT_PATHS, _CANDIDATE_AGENTS, _OPPONENT_AGENTS
    _ENGINE_PATH = engine_path
    _OPPONENT_PATHS = opponent_paths
    _CANDIDATE_AGENTS = {}
    _OPPONENT_AGENTS = {}


def play(task: tuple[dict[str, Any], str, str, int, int]) -> dict[str, Any]:
    values, key, opponent, seed, seat = task
    try:
        candidate = _CANDIDATE_AGENTS.get(key)
        if candidate is None:
            engine = load_module(
                Path(_ENGINE_PATH),
                f"paired_engine_{os.getpid()}_{abs(hash(key))}",
            )
            candidate = configure_module(engine, Ev2Genome(**values))
            _CANDIDATE_AGENTS[key] = candidate
        opponent_agent = _OPPONENT_AGENTS.get(opponent)
        if opponent_agent is None:
            opponent_module = load_module(
                Path(_OPPONENT_PATHS[opponent]),
                f"paired_opponent_{os.getpid()}_{opponent}",
            )
            opponent_agent = opponent_module.agent
            _OPPONENT_AGENTS[opponent] = opponent_agent
        agents = (
            [candidate, opponent_agent]
            if seat == 0
            else [opponent_agent, candidate]
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


def candidate(
    genome: Ev2Genome,
    label: str,
    requested: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "genome": genome.normalized(),
        "label": label,
        "requested": dict(requested or {}),
    }


def unique_candidates(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = row["genome"].key()
        unique.setdefault(key, row)
    return list(unique.values())


def active_fields() -> list[str]:
    fields: list[str] = []
    for block_fields in GENE_BLOCKS.values():
        for field in block_fields:
            if field not in fields:
                fields.append(field)
    return fields


def one_dimensional_candidates(base: Ev2Genome) -> list[dict[str, Any]]:
    rows = [candidate(base, "incumbent")]
    values = base.to_dict()
    for field in active_fields():
        current = values[field]
        small = FIELD_STEPS[field][0]
        for direction in (-1, 1):
            proposed = current + direction * small
            if isinstance(current, int):
                proposed = int(round(proposed))
            genome = replace(base, **{field: proposed}).normalized()
            if genome.key() == base.key():
                continue
            rows.append(
                candidate(
                    genome,
                    f"{field}={getattr(genome, field)}",
                    {field: proposed},
                )
            )
    return unique_candidates(rows)


def structural_candidates(base: Ev2Genome) -> list[dict[str, Any]]:
    """Add coherent, non-local hypotheses that coordinate search cannot reach.

    The coordinate neighbourhood is intentionally conservative, but a strong
    fixed-trace rival can expose a different *schedule* involving several
    coupled genes.  These profiles keep those coupled changes together so
    stage 0 can reject or retain the complete idea instead of testing an
    inactive half (for example, a larger herd without enough animal slots).
    """
    profiles = {
        "ev6_late_herd": {
            "target_herd": 16,
            "animal_slots_ne": 6,
            "animal_slots_sw": 5,
            "animal_purchase_last_day": 17,
        },
        "ev6_expansion": {
            "first_land_day": 9,
            "second_land_day": 12,
        },
        "ev6_three_stage": {
            "max_hands": 11,
            "core_herd": 4,
            "mid_herd": 9,
            "target_herd": 16,
            "herd_expansion_day": 7,
            "herd_final_day": 11,
            "animal_purchase_last_day": 17,
            "animal_slots_ne": 6,
            "animal_slots_sw": 5,
            "first_land_day": 9,
            "second_land_day": 12,
        },
        "ev6_herd_current_land": {
            "core_herd": 4,
            "mid_herd": 9,
            "target_herd": 16,
            "herd_expansion_day": 7,
            "herd_final_day": 11,
            "animal_purchase_last_day": 17,
            "animal_slots_ne": 6,
            "animal_slots_sw": 5,
        },
    }
    rows = []
    for label, requested in profiles.items():
        rows.append(
            candidate(
                replace(base, **requested).normalized(),
                label,
                requested,
            )
        )
    return unique_candidates(rows)


def paired_summary(
    row: dict[str, Any],
    games: list[dict[str, Any]],
    baseline: dict[tuple[str, int, int], dict[str, Any]],
) -> dict[str, Any]:
    deltas = []
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
    worst_delta = min(value["mean_delta"] for value in by_opponent.values())
    errors = sum(game["error"] is not None for game in games)
    # Mean paired improvement is primary. Penalize uncertainty and regressions
    # on the weakest opponent, but do not double-reward a positive worst case.
    score = mean_delta - 0.5 * stderr + 0.25 * min(0.0, worst_delta)
    if errors:
        score -= 1_000_000.0 * errors
    return {
        "key": row["genome"].key(),
        "label": row["label"],
        "requested": row["requested"],
        "genome": row["genome"].to_dict(),
        "games": len(games),
        "mean_reward": mean(float(game["reward"]) for game in games),
        "mean_margin": mean(float(game["margin"]) for game in games),
        "win_rate": mean(float(bool(game["win"])) for game in games),
        "mean_delta": mean_delta,
        "stderr_delta": stderr,
        "lower_95_delta": mean_delta - 1.96 * stderr,
        "worst_opponent_delta": worst_delta,
        "paired_score": score,
        "errors": errors,
        "by_opponent": by_opponent,
    }


def evaluate(
    pool: Any,
    rows: list[dict[str, Any]],
    opponents: list[str],
    seeds: list[int],
    incumbent_key: str,
) -> list[dict[str, Any]]:
    rows = unique_candidates(rows)
    tasks = [
        (row["genome"].to_dict(), row["genome"].key(), opponent, seed, seat)
        for row in rows
        for opponent in opponents
        for seed in seeds
        for seat in (0, 1)
    ]
    games_by_key: dict[str, list[dict[str, Any]]] = {
        row["genome"].key(): [] for row in rows
    }
    for game in pool.imap_unordered(play, tasks, chunksize=1):
        games_by_key[game["key"]].append(game)
    baseline_games = games_by_key[incumbent_key]
    baseline = {
        (game["opponent"], int(game["seed"]), int(game["seat"])): game
        for game in baseline_games
    }
    summaries = [
        paired_summary(row, games_by_key[row["genome"].key()], baseline)
        for row in rows
    ]
    summaries.sort(key=lambda result: result["paired_score"], reverse=True)
    return summaries


def rows_from_summaries(summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        candidate(
            Ev2Genome(**summary["genome"]),
            str(summary["label"]),
            dict(summary["requested"]),
        )
        for summary in summaries
    ]


def top_unique_fields(
    summaries: list[dict[str, Any]], count: int
) -> list[dict[str, Any]]:
    selected = []
    seen = set()
    for summary in summaries:
        requested = dict(summary["requested"])
        if len(requested) != 1:
            continue
        field = next(iter(requested))
        if field in seen:
            continue
        seen.add(field)
        selected.append(summary)
        if len(selected) >= count:
            break
    return selected


def pairwise_candidates(
    base: Ev2Genome, singles: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    rows = [candidate(base, "incumbent"), *rows_from_summaries(singles)]
    for index, first in enumerate(singles):
        for second in singles[index + 1 :]:
            requested = {**first["requested"], **second["requested"]}
            genome = replace(base, **requested).normalized()
            label = "+".join(f"{key}={value}" for key, value in requested.items())
            rows.append(candidate(genome, label, requested))
    return unique_candidates(rows)


def seeds(start: int, count: int) -> list[int]:
    return [start + index * 31 for index in range(count)]


def save_stage(
    output_dir: Path,
    name: str,
    stage_seeds: list[int],
    summaries: list[dict[str, Any]],
) -> None:
    (output_dir / f"{name}.json").write_text(
        json.dumps({"seeds": stage_seeds, "results": summaries}, indent=2) + "\n",
        encoding="utf-8",
    )
    best = summaries[0]
    print(
        f"{name}: {best['label']} delta={best['mean_delta']:+.1f} "
        f"lower95={best['lower_95_delta']:+.1f} "
        f"worst={best['worst_opponent_delta']:+.1f}",
        flush=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--incumbent", type=Path, default=ROOT / "main.py")
    parser.add_argument("--engine", type=Path, default=ROOT / "test/0801_ev4/main.py")
    parser.add_argument("--models-dir", type=Path, default=ROOT / "test")
    parser.add_argument("--opponents", nargs="*", default=list(DEFAULT_OPPONENTS))
    parser.add_argument("--workers", type=int, default=20)
    parser.add_argument("--seed-start", type=int, default=10_100_000)
    parser.add_argument("--stage0-seeds", type=int, default=4)
    parser.add_argument("--stage1-seeds", type=int, default=16)
    parser.add_argument("--stage2-seeds", type=int, default=24)
    parser.add_argument("--final-seeds", type=int, default=100)
    parser.add_argument("--stage1-count", type=int, default=20)
    parser.add_argument("--top-fields", type=int, default=5)
    parser.add_argument("--finalists", type=int, default=3)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    base = incumbent_genome(args.incumbent.resolve())
    incumbent_key = base.key()
    opponent_paths = {
        name: (args.models_dir.resolve() / name / "main.py")
        for name in args.opponents
    }
    required = [args.engine.resolve(), *opponent_paths.values()]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise SystemExit("missing file(s): " + ", ".join(missing))
    metadata = {
        "method": "paired coordinate + structural racing v2",
        "incumbent": str(args.incumbent.resolve()),
        "engine": str(args.engine.resolve()),
        "opponents": {name: str(path) for name, path in opponent_paths.items()},
        "baseline": base.to_dict(),
        "stage0_seeds": args.stage0_seeds,
        "stage1_seeds": args.stage1_seeds,
        "stage2_seeds": args.stage2_seeds,
        "final_seeds": args.final_seeds,
        "stage1_count": args.stage1_count,
        "top_fields": args.top_fields,
        "finalists": args.finalists,
    }
    (output_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )

    context = mp.get_context("spawn")
    workers = max(1, min(args.workers, os.cpu_count() or args.workers))
    with context.Pool(
        workers,
        initializer=worker_init,
        initargs=(
            str(args.engine.resolve()),
            {name: str(path) for name, path in opponent_paths.items()},
        ),
    ) as pool:
        stage0_seed_values = seeds(args.seed_start, args.stage0_seeds)
        stage0 = evaluate(
            pool,
            unique_candidates(
                one_dimensional_candidates(base) + structural_candidates(base)
            ),
            list(opponent_paths),
            stage0_seed_values,
            incumbent_key,
        )
        save_stage(output_dir, "stage0_coordinate", stage0_seed_values, stage0)

        incumbent_summary = next(row for row in stage0 if row["key"] == incumbent_key)
        stage1_inputs = [incumbent_summary] + [
            row for row in stage0 if row["key"] != incumbent_key
        ][: args.stage1_count]
        structural_keys = {
            row["genome"].key() for row in structural_candidates(base)
        }
        stage1_inputs += [
            row
            for row in stage0
            if row["key"] in structural_keys
        ]
        stage1_seed_values = seeds(args.seed_start + 100_000, args.stage1_seeds)
        stage1 = evaluate(
            pool,
            unique_candidates(rows_from_summaries(stage1_inputs)),
            list(opponent_paths),
            stage1_seed_values,
            incumbent_key,
        )
        save_stage(output_dir, "stage1_race", stage1_seed_values, stage1)

        singles = top_unique_fields(
            [row for row in stage1 if row["key"] != incumbent_key],
            args.top_fields,
        )
        # Keep coherent multi-gene profiles alive.  They cannot be rebuilt by
        # pairwise_candidates(), which deliberately combines only two singles.
        structural = [
            row
            for row in stage1
            if row["key"] != incumbent_key and len(row["requested"]) > 1
        ][: args.top_fields]
        stage2_inputs = unique_candidates(
            pairwise_candidates(base, singles) + rows_from_summaries(structural)
        )
        stage2_seed_values = seeds(args.seed_start + 200_000, args.stage2_seeds)
        stage2 = evaluate(
            pool,
            stage2_inputs,
            list(opponent_paths),
            stage2_seed_values,
            incumbent_key,
        )
        save_stage(output_dir, "stage2_pairwise", stage2_seed_values, stage2)

        stage2_incumbent = next(row for row in stage2 if row["key"] == incumbent_key)
        final_inputs = [stage2_incumbent] + [
            row for row in stage2 if row["key"] != incumbent_key
        ][: args.finalists]
        final_seed_values = seeds(args.seed_start + 300_000, args.final_seeds)
        final = evaluate(
            pool,
            rows_from_summaries(final_inputs),
            list(opponent_paths),
            final_seed_values,
            incumbent_key,
        )
        save_stage(output_dir, "final_heldout", final_seed_values, final)

    best_overall = final[0]
    eligible = [
        row
        for row in final
        if row["key"] != incumbent_key
        and row["errors"] == 0
        and row["lower_95_delta"] > 0
        and row["worst_opponent_delta"] >= 0
    ]
    accepted = bool(eligible)
    selected_result = eligible[0] if eligible else next(
        row for row in final if row["key"] == incumbent_key
    )
    decision = {
        "accepted": accepted,
        "reason": (
            "positive held-out 95% lower bound and no opponent regression"
            if accepted
            else "held-out acceptance gate not met"
        ),
        "best_overall": best_overall,
        "selected": selected_result,
    }
    (output_dir / "decision.json").write_text(
        json.dumps(decision, indent=2) + "\n", encoding="utf-8"
    )
    selected = Ev2Genome(**selected_result["genome"]) if accepted else base
    (output_dir / "best_genome.json").write_text(
        json.dumps(selected.to_dict(), indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"decision accepted={accepted} label={selected_result['label']} "
        f"delta={selected_result['mean_delta']:+.1f} "
        f"lower95={selected_result['lower_95_delta']:+.1f} "
        f"worst={selected_result['worst_opponent_delta']:+.1f}"
    )
    print(f"wrote {output_dir}")


if __name__ == "__main__":
    main()

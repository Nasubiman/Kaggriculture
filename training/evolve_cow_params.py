#!/usr/bin/env python3
"""Time-bounded evolutionary tuning for the current Cow Crown agent.

This search deliberately optimizes the existing semantic policy instead of
trying to learn 720 turns of raw actions from scratch.  It needs no replay
dataset and parallelizes complete Kaggriculture games across CPU workers.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import multiprocessing as mp
import os
import random
import re
import time
from pathlib import Path
from statistics import mean
from types import SimpleNamespace
from typing import Any

from kaggle_environments import make


ROOT = Path(__file__).resolve().parents[1]

BASELINE_PARAMS: dict[str, int | float] = {
    "COW_START_DAY": 8,
    "COW_TARGET": 16,
    "COW_PURCHASE_BATCH": 4,
    "COW_HANDS": 11,
    "WHEAT_TILES": 3,
    "WHEAT_PICKUP_BATCH": 12,
    "SALE_PROCEEDS_FACTOR": 0.5,
    "SHEEP_TARGET": 4,
    "OPENING_HANDS": 7,
}

PARAM_VALUES: dict[str, tuple[int | float, ...]] = {
    "COW_START_DAY": tuple(range(8, 15)),
    "COW_TARGET": tuple(range(15, 29)),
    "COW_PURCHASE_BATCH": tuple(range(4, 21, 2)),
    "COW_HANDS": tuple(range(8, 17)),
    "WHEAT_TILES": tuple(range(0, 7)),
    "WHEAT_PICKUP_BATCH": tuple(range(2, 17, 2)),
    "SALE_PROCEEDS_FACTOR": tuple(
        round(value / 100, 2) for value in range(45, 96, 5)
    ),
    "SHEEP_TARGET": tuple(range(0, 5)),
    "OPENING_HANDS": tuple(range(5, 11)),
}

OPPONENT_WEIGHTS = {
    "incumbent": 3.0,
    "pulse": 1.0,
    "score800": 1.0,
}

_WORKER_CANDIDATE: Any = None
_WORKER_OPPONENTS: dict[str, Any] = {}


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load Python module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_pasted_agent(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    marker = "%%writefile /kaggle/working/main.py"
    source = text.split(marker, 1)[1] if marker in text else text
    writing_marker = "Writing /kaggle/working/main.py"
    source = source.rsplit(writing_marker, 1)[0]
    namespace: dict[str, Any] = {}
    exec(compile(source, str(path), "exec"), namespace)
    return SimpleNamespace(agent=namespace["agent"])


def normalize_params(
    values: dict[str, int | float],
) -> dict[str, int | float]:
    normalized = {}
    for name, choices in PARAM_VALUES.items():
        value = values.get(name, BASELINE_PARAMS[name])
        normalized[name] = min(
            choices,
            key=lambda choice: abs(float(choice) - float(value)),
        )

    # The top half contains 50 cells.  Leave enough room for sheep and wheat.
    capacity = 50 - int(normalized["SHEEP_TARGET"]) - int(
        normalized["WHEAT_TILES"]
    )
    normalized["COW_TARGET"] = min(
        int(normalized["COW_TARGET"]),
        max(15, capacity),
    )
    return normalized


def params_key(values: dict[str, int | float]) -> str:
    normalized = normalize_params(values)
    return "|".join(f"{name}={normalized[name]}" for name in PARAM_VALUES)


def apply_params(module: Any, values: dict[str, int | float]) -> None:
    normalized = normalize_params(values)
    for name, value in normalized.items():
        if name == "OPENING_HANDS":
            module.crop_agent.TARGET_HANDS = int(value)
        else:
            setattr(module, name, value)


def worker_init(repo: str, score800_reference: str | None) -> None:
    global _WORKER_CANDIDATE, _WORKER_OPPONENTS

    root = Path(repo)
    suffix = str(os.getpid())
    _WORKER_CANDIDATE = load_module(
        root / "main.py",
        f"evolution_candidate_{suffix}",
    )
    _WORKER_OPPONENTS = {
        "incumbent": load_module(
            root / "main.py",
            f"evolution_incumbent_{suffix}",
        ).agent,
        "pulse": load_module(
            root / "agents" / "pulse_breaker_v2.py",
            f"evolution_pulse_{suffix}",
        ).agent,
    }
    if score800_reference:
        _WORKER_OPPONENTS["score800"] = load_pasted_agent(
            Path(score800_reference)
        ).agent


def play_task(
    task: tuple[
        str,
        dict[str, int | float],
        str,
        int,
        int,
    ],
) -> dict[str, Any]:
    candidate_id, params, opponent_name, seed, seat = task
    try:
        apply_params(_WORKER_CANDIDATE, params)
        opponent = _WORKER_OPPONENTS[opponent_name]
        agents = (
            [_WORKER_CANDIDATE.agent, opponent]
            if seat == 0
            else [opponent, _WORKER_CANDIDATE.agent]
        )
        env = make(
            "kaggriculture",
            configuration={"episodeSteps": 720, "seed": seed},
            debug=False,
        )
        env.run(agents)
        final = env.steps[-1]
        reward = float(final[seat].reward)
        opponent_reward = float(final[1 - seat].reward)
        return {
            "candidate_id": candidate_id,
            "opponent": opponent_name,
            "seed": seed,
            "seat": seat,
            "reward": reward,
            "opponent_reward": opponent_reward,
            "margin": reward - opponent_reward,
            "win": reward > opponent_reward,
            "tie": reward == opponent_reward,
            "status": final[seat].status,
            "error": None,
        }
    except Exception as error:  # pragma: no cover - surfaced in run logs
        return {
            "candidate_id": candidate_id,
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


def game_utility(game: dict[str, Any]) -> float:
    outcome = 1.0 if game["win"] else 0.5 if game["tie"] else 0.0
    margin_term = math.tanh(float(game["margin"]) / 25_000.0)
    reward_term = max(-1.0, min(2.0, float(game["reward"]) / 100_000.0))
    return 2.0 * outcome + margin_term + 0.25 * reward_term


def summarize_games(games: list[dict[str, Any]]) -> dict[str, Any]:
    if not games:
        return {
            "objective": -1_000_000.0,
            "games": 0,
            "wins": 0,
            "ties": 0,
            "win_rate": 0.0,
            "mean_reward": -1_000_000.0,
            "mean_margin": -1_000_000.0,
            "errors": 1,
            "by_opponent": {},
        }

    by_opponent: dict[str, list[dict[str, Any]]] = {}
    for game in games:
        by_opponent.setdefault(str(game["opponent"]), []).append(game)

    weighted_utility = 0.0
    total_weight = 0.0
    opponent_summaries = {}
    for opponent, opponent_games in by_opponent.items():
        utility = mean(game_utility(game) for game in opponent_games)
        weight = OPPONENT_WEIGHTS.get(opponent, 1.0)
        weighted_utility += utility * weight
        total_weight += weight
        opponent_summaries[opponent] = {
            "games": len(opponent_games),
            "wins": sum(bool(game["win"]) for game in opponent_games),
            "ties": sum(bool(game["tie"]) for game in opponent_games),
            "mean_reward": mean(
                float(game["reward"]) for game in opponent_games
            ),
            "mean_margin": mean(
                float(game["margin"]) for game in opponent_games
            ),
            "utility": utility,
        }

    return {
        "objective": weighted_utility / max(total_weight, 1.0),
        "games": len(games),
        "wins": sum(bool(game["win"]) for game in games),
        "ties": sum(bool(game["tie"]) for game in games),
        "win_rate": mean(float(bool(game["win"])) for game in games),
        "mean_reward": mean(float(game["reward"]) for game in games),
        "mean_margin": mean(float(game["margin"]) for game in games),
        "errors": sum(game["error"] is not None for game in games),
        "by_opponent": opponent_summaries,
    }


def evaluate_population(
    pool: Any,
    candidates: list[dict[str, int | float]],
    schedule: dict[str, list[int]],
) -> dict[str, dict[str, Any]]:
    tasks = []
    params_by_id = {}
    for params in candidates:
        candidate_id = params_key(params)
        params_by_id[candidate_id] = normalize_params(params)
        for opponent, seeds in schedule.items():
            for seed in seeds:
                for seat in (0, 1):
                    tasks.append(
                        (
                            candidate_id,
                            params_by_id[candidate_id],
                            opponent,
                            seed,
                            seat,
                        )
                    )

    games_by_id = {candidate_id: [] for candidate_id in params_by_id}
    for game in pool.imap_unordered(play_task, tasks, chunksize=1):
        games_by_id[game["candidate_id"]].append(game)

    return {
        candidate_id: {
            "params": params_by_id[candidate_id],
            **summarize_games(games),
        }
        for candidate_id, games in games_by_id.items()
    }


def mutate_params(
    parent: dict[str, int | float],
    rng: random.Random,
) -> dict[str, int | float]:
    child = normalize_params(parent)
    mutation_count = rng.choices((1, 2, 3, 4), weights=(35, 40, 20, 5))[0]
    for name in rng.sample(list(PARAM_VALUES), mutation_count):
        choices = PARAM_VALUES[name]
        current_index = min(
            range(len(choices)),
            key=lambda index: abs(
                float(choices[index]) - float(child[name])
            ),
        )
        if rng.random() < 0.2:
            new_index = rng.randrange(len(choices))
        else:
            step = rng.choice((-2, -1, 1, 2))
            new_index = max(0, min(len(choices) - 1, current_index + step))
        child[name] = choices[new_index]
    return normalize_params(child)


def build_population(
    elites: list[dict[str, Any]],
    size: int,
    rng: random.Random,
) -> list[dict[str, int | float]]:
    parents = [record["params"] for record in elites] or [BASELINE_PARAMS]
    population = [
        normalize_params(BASELINE_PARAMS),
        normalize_params(parents[0]),
    ]
    seen = {params_key(params) for params in population}
    attempts = 0
    while len(population) < size and attempts < size * 100:
        attempts += 1
        rank = min(
            int(rng.expovariate(0.9)),
            len(parents) - 1,
        )
        child = mutate_params(parents[rank], rng)
        key = params_key(child)
        if key not in seen:
            seen.add(key)
            population.append(child)
    return population


def render_agent(
    source_path: Path,
    output_path: Path,
    params: dict[str, int | float],
) -> None:
    source = source_path.read_text(encoding="utf-8")
    normalized = normalize_params(params)
    for name, value in normalized.items():
        if name == "OPENING_HANDS":
            pattern = r"^    TARGET_HANDS = .+$"
            replacement = f"    TARGET_HANDS = {int(value)}"
        else:
            pattern = rf"^{re.escape(name)} = .+$"
            replacement = f"{name} = {value!r}"
        source, count = re.subn(
            pattern,
            replacement,
            source,
            count=1,
            flags=re.MULTILINE,
        )
        if count != 1:
            raise RuntimeError(f"Could not render parameter {name}")
    output_path.write_text(source, encoding="utf-8")


def save_state(
    output_dir: Path,
    generation: int,
    elapsed_seconds: float,
    validated: dict[str, dict[str, Any]],
    final: dict[str, Any] | None = None,
) -> None:
    ranked = sorted(
        validated.values(),
        key=lambda record: record["objective"],
        reverse=True,
    )
    state = {
        "generation": generation,
        "elapsed_seconds": elapsed_seconds,
        "best": final or (ranked[0] if ranked else None),
        "top_validated": ranked[:20],
    }
    temporary = output_dir / "search_state.json.tmp"
    temporary.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output_dir / "search_state.json")


def available_schedule(
    schedule: dict[str, list[int]],
    have_score800: bool,
) -> dict[str, list[int]]:
    return {
        opponent: seeds
        for opponent, seeds in schedule.items()
        if opponent != "score800" or have_score800
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--minutes", type=float, default=90.0)
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 4) - 2))
    parser.add_argument("--population", type=int, default=20)
    parser.add_argument("--shortlist", type=int, default=4)
    parser.add_argument("--seed", type=int, default=20260731)
    parser.add_argument("--repo", type=Path, default=ROOT)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--score800-reference", type=Path)
    args = parser.parse_args()

    repo = args.repo.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    score800_reference = (
        str(args.score800_reference.resolve())
        if args.score800_reference
        else None
    )
    have_score800 = bool(
        score800_reference and Path(score800_reference).exists()
    )
    workers = max(1, min(args.workers, os.cpu_count() or args.workers))
    rng = random.Random(args.seed)
    deadline = time.monotonic() + args.minutes * 60.0

    metadata = {
        "started_at_unix": time.time(),
        "minutes": args.minutes,
        "workers": workers,
        "population": args.population,
        "shortlist": args.shortlist,
        "seed": args.seed,
        "repo": str(repo),
        "score800_reference": score800_reference,
        "baseline_params": BASELINE_PARAMS,
        "parameter_values": {
            name: list(values) for name, values in PARAM_VALUES.items()
        },
    }
    (output_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n",
        encoding="utf-8",
    )

    context = mp.get_context("spawn")
    validated: dict[str, dict[str, Any]] = {}
    elites = [{"params": normalize_params(BASELINE_PARAMS), "objective": -1e9}]
    generation = 0
    started = time.monotonic()

    print(
        f"starting evolution: minutes={args.minutes} workers={workers} "
        f"population={args.population} score800={have_score800}",
        flush=True,
    )

    with context.Pool(
        workers,
        initializer=worker_init,
        initargs=(str(repo), score800_reference),
    ) as pool:
        while time.monotonic() < deadline:
            population = build_population(
                elites,
                max(4, args.population),
                rng,
            )
            base_seed = 10_000 + (generation % 200) * 10
            quick_schedule = available_schedule(
                {
                    "incumbent": [base_seed, base_seed + 1],
                    "pulse": [base_seed + 2],
                    "score800": [base_seed + 3],
                },
                have_score800,
            )
            quick = evaluate_population(pool, population, quick_schedule)
            quick_ranked = sorted(
                quick.values(),
                key=lambda record: record["objective"],
                reverse=True,
            )
            shortlist = quick_ranked[: max(1, args.shortlist)]

            validation_schedule = available_schedule(
                {
                    "incumbent": [90_001, 90_002, 90_003],
                    "pulse": [91_001],
                    "score800": [92_001],
                },
                have_score800,
            )
            new_validation = [
                record["params"]
                for record in shortlist
                if params_key(record["params"]) not in validated
            ]
            if new_validation:
                validated.update(
                    evaluate_population(
                        pool,
                        new_validation,
                        validation_schedule,
                    )
                )

            validation_ranked = sorted(
                validated.values(),
                key=lambda record: record["objective"],
                reverse=True,
            )
            elites = validation_ranked[:8]
            generation += 1
            elapsed = time.monotonic() - started
            save_state(output_dir, generation, elapsed, validated)
            best = elites[0]
            print(
                f"generation={generation} elapsed={elapsed:.1f}s "
                f"validated={len(validated)} "
                f"best={best['objective']:.6f} "
                f"wins={best['wins']}/{best['games']} "
                f"reward={best['mean_reward']:.1f} "
                f"margin={best['mean_margin']:+.1f} "
                f"params={best['params']}",
                flush=True,
            )

            # Do not launch another full generation near the deadline.
            if deadline - time.monotonic() < 45:
                break

        selection_candidates = [
            record["params"]
            for record in sorted(
                validated.values(),
                key=lambda record: record["objective"],
                reverse=True,
            )[:8]
        ]
        if normalize_params(BASELINE_PARAMS) not in selection_candidates:
            selection_candidates.append(normalize_params(BASELINE_PARAMS))

        selection_schedule = available_schedule(
            {
                "incumbent": [130_001, 130_002, 130_003, 130_004, 130_005],
                "pulse": [131_001, 131_002],
                "score800": [132_001, 132_002],
            },
            have_score800,
        )
        selected = evaluate_population(
            pool,
            selection_candidates,
            selection_schedule,
        )

    selected_ranked = sorted(
        selected.values(),
        key=lambda record: record["objective"],
        reverse=True,
    )
    final = selected_ranked[0]
    elapsed = time.monotonic() - started
    save_state(output_dir, generation, elapsed, validated, final=final)
    (output_dir / "selection_results.json").write_text(
        json.dumps(selected_ranked, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "best_params.json").write_text(
        json.dumps(final, indent=2) + "\n",
        encoding="utf-8",
    )
    render_agent(
        repo / "main.py",
        output_dir / "best_agent.py",
        final["params"],
    )
    print(
        f"finished elapsed={elapsed:.1f}s objective={final['objective']:.6f} "
        f"wins={final['wins']}/{final['games']} "
        f"reward={final['mean_reward']:.1f} "
        f"margin={final['mean_margin']:+.1f}",
        flush=True,
    )
    print(f"best params: {final['params']}", flush=True)
    print(f"wrote {output_dir}", flush=True)


if __name__ == "__main__":
    main()

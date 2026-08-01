#!/usr/bin/env python3
"""Run a round-robin league for every test/<name>/main.py model."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import multiprocessing as mp
import os
from itertools import combinations
from pathlib import Path
from statistics import mean
from typing import Any

from fast_kaggriculture import run_fast_episode


ROOT = Path(__file__).resolve().parents[1]
_MODEL_PATHS: dict[str, str] = {}
_FAST_RUNNER = True


def load_agent(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    agent = getattr(module, "agent", None)
    if not callable(agent):
        raise RuntimeError(f"{path} does not define a callable agent")
    return agent


def discover(models_dir: Path, selected: list[str]) -> dict[str, Path]:
    available = {
        path.parent.name: path.resolve()
        for path in sorted(models_dir.glob("*/main.py"))
        if path.is_file()
    }
    if selected:
        missing = sorted(set(selected) - set(available))
        if missing:
            raise SystemExit(f"unknown test model(s): {', '.join(missing)}")
        return {name: available[name] for name in selected}
    if len(available) < 2:
        raise SystemExit(f"need at least two models below {models_dir}")
    return available


def worker_init(model_paths: dict[str, str], fast_runner: bool) -> None:
    global _MODEL_PATHS, _FAST_RUNNER
    _MODEL_PATHS = model_paths
    _FAST_RUNNER = fast_runner


def play(task: tuple[str, str, int, int]) -> dict[str, Any]:
    model_a, model_b, seed, seat_a = task
    suffix = f"{os.getpid()}_{model_a}_{model_b}_{seed}_{seat_a}"
    try:
        agent_a = load_agent(Path(_MODEL_PATHS[model_a]), f"matrix_a_{suffix}")
        agent_b = load_agent(Path(_MODEL_PATHS[model_b]), f"matrix_b_{suffix}")
        agents = [agent_a, agent_b] if seat_a == 0 else [agent_b, agent_a]
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
        reward_a = float(final[seat_a].reward)
        reward_b = float(final[1 - seat_a].reward)
        return {
            "model_a": model_a,
            "model_b": model_b,
            "seed": seed,
            "seat_a": seat_a,
            "reward_a": reward_a,
            "reward_b": reward_b,
            "margin_a": reward_a - reward_b,
            "status_a": str(final[seat_a].status),
            "status_b": str(final[1 - seat_a].status),
            "error": None,
        }
    except Exception as error:
        return {
            "model_a": model_a,
            "model_b": model_b,
            "seed": seed,
            "seat_a": seat_a,
            "reward_a": -1_000_000.0,
            "reward_b": -1_000_000.0,
            "margin_a": 0.0,
            "status_a": "ERROR",
            "status_b": "ERROR",
            "error": repr(error),
        }


def perspective(game: dict[str, Any], model: str) -> dict[str, Any]:
    is_a = game["model_a"] == model
    reward = float(game["reward_a"] if is_a else game["reward_b"])
    opponent_reward = float(game["reward_b"] if is_a else game["reward_a"])
    return {
        "reward": reward,
        "opponent_reward": opponent_reward,
        "margin": reward - opponent_reward,
        "win": reward > opponent_reward,
        "tie": reward == opponent_reward,
        "error": game["error"],
    }


def summarize(games: list[dict[str, Any]], model: str) -> dict[str, Any]:
    rows = [perspective(game, model) for game in games]
    return {
        "games": len(rows),
        "wins": sum(bool(row["win"]) for row in rows),
        "ties": sum(bool(row["tie"]) for row in rows),
        "win_rate": mean(float(bool(row["win"])) for row in rows),
        "mean_reward": mean(float(row["reward"]) for row in rows),
        "mean_opponent_reward": mean(
            float(row["opponent_reward"]) for row in rows
        ),
        "mean_margin": mean(float(row["margin"]) for row in rows),
        "errors": sum(row["error"] is not None for row in rows),
    }


def matrix_markdown(
    names: list[str], summaries: dict[str, dict[str, dict[str, Any]]]
) -> str:
    lines = [
        "# Test model round-robin",
        "",
        "Each cell is the row model's result against the column model.",
        "Every seed is played from both seats.",
        "",
        "## Win rate",
        "",
        "| model | " + " | ".join(names) + " |",
        "|---|" + "---:|" * len(names),
    ]
    for row in names:
        cells = [
            "—" if row == column else f"{summaries[row][column]['win_rate']:.1%}"
            for column in names
        ]
        lines.append("| " + row + " | " + " | ".join(cells) + " |")

    lines.extend(
        [
            "",
            "## Mean margin",
            "",
            "| model | " + " | ".join(names) + " |",
            "|---|" + "---:|" * len(names),
        ]
    )
    for row in names:
        cells = [
            "—"
            if row == column
            else f"{summaries[row][column]['mean_margin']:+.1f}"
            for column in names
        ]
        lines.append("| " + row + " | " + " | ".join(cells) + " |")

    lines.extend(
        [
            "",
            "## Overall",
            "",
            "| model | games | win rate | mean reward | mean margin | errors |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for model in names:
        opponents = [summaries[model][other] for other in names if other != model]
        games = sum(int(row["games"]) for row in opponents)
        wins = sum(int(row["wins"]) for row in opponents)
        reward = sum(row["mean_reward"] * row["games"] for row in opponents) / games
        margin = sum(row["mean_margin"] * row["games"] for row in opponents) / games
        errors = sum(int(row["errors"]) for row in opponents)
        lines.append(
            f"| {model} | {games} | {wins / games:.1%} | {reward:.1f} | "
            f"{margin:+.1f} | {errors} |"
        )
    return "\n".join(lines) + "\n"


def write_csv_matrix(
    path: Path,
    names: list[str],
    summaries: dict[str, dict[str, dict[str, Any]]],
    field: str,
) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["model", *names])
        for row in names:
            writer.writerow(
                [row]
                + [
                    "" if row == column else summaries[row][column][field]
                    for column in names
                ]
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models-dir", type=Path, default=ROOT / "test")
    parser.add_argument("--models", nargs="*", default=[])
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--seed-start", type=int, default=9_850_000)
    parser.add_argument("--workers", type=int, default=20)
    parser.add_argument(
        "--fast-runner", action=argparse.BooleanOptionalAction, default=True
    )
    parser.add_argument(
        "--output-dir", type=Path, default=ROOT / "reports/test_matrix"
    )
    args = parser.parse_args()

    models = discover(args.models_dir.resolve(), args.models)
    names = sorted(models)
    if len(names) < 2:
        raise SystemExit("select at least two models")
    seeds = [args.seed_start + index * 17 for index in range(args.seeds)]
    tasks = [
        (model_a, model_b, seed, seat_a)
        for model_a, model_b in combinations(names, 2)
        for seed in seeds
        for seat_a in (0, 1)
    ]
    context = mp.get_context("spawn")
    workers = max(1, min(args.workers, os.cpu_count() or args.workers))
    with context.Pool(
        workers,
        initializer=worker_init,
        initargs=({name: str(path) for name, path in models.items()}, args.fast_runner),
    ) as pool:
        games = list(pool.imap_unordered(play, tasks, chunksize=1))
    games.sort(
        key=lambda game: (
            game["model_a"], game["model_b"], game["seed"], game["seat_a"]
        )
    )

    summaries: dict[str, dict[str, dict[str, Any]]] = {name: {} for name in names}
    for model_a, model_b in combinations(names, 2):
        pair_games = [
            game
            for game in games
            if game["model_a"] == model_a and game["model_b"] == model_b
        ]
        summaries[model_a][model_b] = summarize(pair_games, model_a)
        summaries[model_b][model_a] = summarize(pair_games, model_b)

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "models_dir": str(args.models_dir.resolve()),
        "models": {name: str(models[name]) for name in names},
        "fast_runner": args.fast_runner,
        "seed_start": args.seed_start,
        "seeds": seeds,
        "games_per_pair": 2 * len(seeds),
        "summaries": summaries,
        "games": games,
    }
    (output_dir / "matrix.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    write_csv_matrix(output_dir / "win_rates.csv", names, summaries, "win_rate")
    write_csv_matrix(output_dir / "mean_margins.csv", names, summaries, "mean_margin")
    report = matrix_markdown(names, summaries)
    (output_dir / "summary.md").write_text(report, encoding="utf-8")
    print(report)
    print(f"wrote {output_dir}")


if __name__ == "__main__":
    main()

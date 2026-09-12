#!/usr/bin/env python3
"""Search small opening-market variants on top of the public V37 agent.

Every candidate finishes turn zero with the same net wheat inventory as V37.
This isolates market timing from the route tape and makes the experiment safe:
the remaining 719-turn policy is byte-for-byte identical to the public model.
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import multiprocessing as mp
import os
import shutil
import tempfile
from pathlib import Path
from statistics import mean
from typing import Any

from fast_kaggriculture import run_fast_episode


ROOT = Path(__file__).resolve().parents[1]
OPENING_PREFIX = "_R42_OPENING="
_CANDIDATES: dict[str, str] = {}
_OPPONENTS: dict[str, str] = {}


def load_agent(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.agent


def opening_literal(actions: list[list[Any]]) -> str:
    return "_R42_OPENING=" + repr(actions)


def candidate_openings(incumbent: list[list[Any]]) -> dict[str, list[list[Any]]]:
    rows: dict[str, list[list[Any]]] = {
        "incumbent": incumbent,
        "buy13_only": [["BUY_PRODUCT", "WHEAT", 13]],
    }
    for quantity in range(5, 101, 5):
        rows[f"roundtrip_q{quantity}"] = [
            ["BUY_PRODUCT", "WHEAT", 13],
            ["BUY_PRODUCT", "WHEAT", quantity],
            ["SELL", "WHEAT", quantity],
        ]
        rows[f"roundtrip_first_q{quantity}"] = [
            ["BUY_PRODUCT", "WHEAT", quantity],
            ["SELL", "WHEAT", quantity],
            ["BUY_PRODUCT", "WHEAT", 13],
        ]
        rows[f"combined_q{quantity}"] = [
            ["BUY_PRODUCT", "WHEAT", 13 + quantity],
            ["SELL", "WHEAT", quantity],
        ]
        rows[f"split_buy_q{quantity}"] = [
            ["BUY_PRODUCT", "WHEAT", quantity],
            ["BUY_PRODUCT", "WHEAT", 13],
            ["SELL", "WHEAT", quantity],
        ]
        for tail in (5, 15, 30):
            rows[f"sell_buy_tail_q{quantity}_t{tail}"] = [
                ["BUY_PRODUCT", "WHEAT", 13 + quantity],
                ["SELL", "WHEAT", quantity + tail],
                ["BUY_PRODUCT", "WHEAT", tail],
            ]
    return rows


def opening_line(source: str) -> tuple[str, list[list[Any]]]:
    matches = [line for line in source.splitlines() if line.startswith(OPENING_PREFIX)]
    if len(matches) != 1:
        raise SystemExit("opening marker is missing or ambiguous")
    try:
        actions = ast.literal_eval(matches[0][len(OPENING_PREFIX) :])
    except (SyntaxError, ValueError) as error:
        raise SystemExit(f"cannot parse incumbent opening: {error}") from error
    if not isinstance(actions, list):
        raise SystemExit("incumbent opening is not a list")
    return matches[0], actions


def worker_init(candidates: dict[str, str], opponents: dict[str, str]) -> None:
    global _CANDIDATES, _OPPONENTS
    _CANDIDATES = candidates
    _OPPONENTS = opponents


def play(task: tuple[str, str, int, int]) -> dict[str, Any]:
    candidate_name, opponent_name, seed, seat = task
    suffix = f"{os.getpid()}_{candidate_name}_{opponent_name}_{seed}_{seat}"
    try:
        candidate = load_agent(Path(_CANDIDATES[candidate_name]), f"candidate_{suffix}")
        opponent = load_agent(Path(_OPPONENTS[opponent_name]), f"opponent_{suffix}")
        agents = [candidate, opponent] if seat == 0 else [opponent, candidate]
        final = run_fast_episode(agents, seed=seed)
        reward = float(final[seat].reward)
        opponent_reward = float(final[1 - seat].reward)
        return {
            "candidate": candidate_name,
            "opponent": opponent_name,
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
            "candidate": candidate_name,
            "opponent": opponent_name,
            "seed": seed,
            "seat": seat,
            "reward": -1_000_000.0,
            "opponent_reward": 0.0,
            "margin": -1_000_000.0,
            "win": False,
            "error": repr(error),
        }


def summarize(games: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "games": len(games),
        "wins": sum(bool(game["win"]) for game in games),
        "mean_margin": mean(float(game["margin"]) for game in games),
        "mean_reward": mean(float(game["reward"]) for game in games),
        "errors": sum(game["error"] is not None for game in games),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=ROOT / "main.py")
    parser.add_argument("--opponents", nargs="*", type=Path, default=[])
    parser.add_argument("--source-results", type=Path)
    parser.add_argument("--candidate-count", type=int, default=0)
    parser.add_argument("--seed-start", type=int, default=9_300_000)
    parser.add_argument("--seeds", type=int, default=8)
    parser.add_argument("--workers", type=int, default=20)
    parser.add_argument("--keep", type=int, default=6)
    parser.add_argument("--output", type=Path, default=ROOT / "reports/public_v37_opening_search.json")
    parser.add_argument("--winner", type=Path, default=ROOT / "candidates/public_v37_opening_stage2/main.py")
    args = parser.parse_args()

    base = args.base.resolve()
    source = base.read_text(encoding="utf-8")
    old, incumbent = opening_line(source)
    openings = candidate_openings(incumbent)
    if args.source_results:
        prior = json.loads(args.source_results.read_text(encoding="utf-8"))
        names = list(prior["ranking"])
        if args.candidate_count > 0:
            names = names[: args.candidate_count]
        names = list(dict.fromkeys([*names, "incumbent"]))
        openings = {
            name: prior["openings"][name] if name != "incumbent" else incumbent
            for name in names
        }
    opponents = args.opponents or [base]
    opponent_paths = {
        (path.parent.name if path.name == "main.py" else path.stem): str(path.resolve())
        for path in opponents
    }
    if len(opponent_paths) != len(opponents):
        raise SystemExit("opponent names are not unique")
    run_dir = Path(tempfile.mkdtemp(prefix="v37-opening-"))
    try:
        paths: dict[str, str] = {}
        for name, actions in openings.items():
            path = run_dir / f"{name}.py"
            path.write_text(source.replace(old, opening_literal(actions)), encoding="utf-8")
            paths[name] = str(path)

        seeds = [args.seed_start + 17 * index for index in range(args.seeds)]
        tasks = [
            (name, opponent, seed, seat)
            for name in paths
            for opponent in opponent_paths
            for seed in seeds
            for seat in (0, 1)
        ]
        context = mp.get_context("spawn")
        workers = max(1, min(args.workers, os.cpu_count() or args.workers))
        with context.Pool(
            workers, initializer=worker_init, initargs=(paths, opponent_paths)
        ) as pool:
            games = list(pool.imap_unordered(play, tasks, chunksize=1))

        summaries = {}
        for name in paths:
            candidate_games = [game for game in games if game["candidate"] == name]
            by_opponent = {
                opponent: summarize(
                    [game for game in candidate_games if game["opponent"] == opponent]
                )
                for opponent in opponent_paths
            }
            summaries[name] = {
                **summarize(candidate_games),
                "by_opponent": by_opponent,
                "worst_margin": min(row["mean_margin"] for row in by_opponent.values()),
                "worst_win_rate": min(
                    row["wins"] / row["games"] for row in by_opponent.values()
                ),
            }
        ranking = sorted(
            summaries,
            key=lambda name: (
                summaries[name]["errors"] == 0,
                summaries[name]["worst_win_rate"],
                summaries[name]["worst_margin"],
                summaries[name]["mean_margin"],
            ),
            reverse=True,
        )
        winner = ranking[0]
        args.winner.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(paths[winner], args.winner)
        result = {
            "base": str(base),
            "opponents": opponent_paths,
            "seeds": seeds,
            "openings": openings,
            "ranking": ranking,
            "summaries": summaries,
            "games": sorted(
                games,
                key=lambda game: (
                    game["candidate"],
                    game["opponent"],
                    game["seed"],
                    game["seat"],
                ),
            ),
            "winner": winner,
            "winner_path": str(args.winner.resolve()),
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        for name in ranking[: max(1, args.keep)]:
            row = summaries[name]
            print(
                f"{name:28} worst_win={row['worst_win_rate']:.1%} "
                f"worst_margin={row['worst_margin']:+.1f} "
                f"mean_margin={row['mean_margin']:+.1f} errors={row['errors']}"
            )
        print(f"winner={winner}")
        print(f"wrote {args.winner}")
        print(f"wrote {args.output}")
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)


if __name__ == "__main__":
    main()

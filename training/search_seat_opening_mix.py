#!/usr/bin/env python3
"""Search deterministic seat-conditioned mixtures of diverse opening orders.

The Kaggriculture player index is known at turn zero.  Assigning a different
opening to each seat gives a reproducible two-component mixture over matches,
without relying on process-global randomness.  Everything after turn zero is
delegated to the unchanged base agent.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import multiprocessing as mp
import os
import shutil
import tempfile
from pathlib import Path
from statistics import mean
from typing import Any

from production_fast_kaggriculture import run_fast_episode


ROOT = Path(__file__).resolve().parents[1]
OPENINGS: dict[str, list[list[Any]]] = {
    "buy13": [["BUY_PRODUCT", "WHEAT", 13]],
    "combined_q5": [["BUY_PRODUCT", "WHEAT", 18], ["SELL", "WHEAT", 5]],
    "public_q30": [
        ["BUY_PRODUCT", "WHEAT", 13],
        ["BUY_PRODUCT", "WHEAT", 30],
        ["SELL", "WHEAT", 30],
    ],
    "combined_q35": [["BUY_PRODUCT", "WHEAT", 48], ["SELL", "WHEAT", 35]],
    "first_q25": [
        ["BUY_PRODUCT", "WHEAT", 25],
        ["SELL", "WHEAT", 25],
        ["BUY_PRODUCT", "WHEAT", 13],
    ],
    "first_q35": [
        ["BUY_PRODUCT", "WHEAT", 35],
        ["SELL", "WHEAT", 35],
        ["BUY_PRODUCT", "WHEAT", 13],
    ],
    "roundtrip_q90": [
        ["BUY_PRODUCT", "WHEAT", 13],
        ["BUY_PRODUCT", "WHEAT", 90],
        ["SELL", "WHEAT", 90],
    ],
}

_CANDIDATES: dict[str, str] = {}
_OPPONENTS: dict[str, str] = {}


def load_agent(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.agent


def wrapper(opening0: list[list[Any]], opening1: list[list[Any]]) -> str:
    return f"""

# Deterministic seat-conditioned opening selected by search_seat_opening_mix.py.
_R55_SEAT_OPENINGS = ({opening0!r}, {opening1!r})
_R55_SEAT_PARENT = agent
def agent(observation, configuration=None):
    result = _R55_SEAT_PARENT(observation, configuration)
    if isinstance(observation, dict) and int(observation.get('step', -1)) == 0:
        result = dict(result)
        result['market'] = [list(order) for order in _R55_SEAT_OPENINGS[int(observation['player'])]]
    return result
agent.telemetry = getattr(_R55_SEAT_PARENT, 'telemetry', {{}})
agent = globals().pop('agent')
"""


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
            "tie": reward == opponent_reward,
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
            "tie": False,
            "error": repr(error),
        }


def summarize(games: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "games": len(games),
        "wins": sum(bool(game["win"]) for game in games),
        "ties": sum(bool(game["tie"]) for game in games),
        "win_rate": mean(float(bool(game["win"])) for game in games),
        "mean_margin": mean(float(game["margin"]) for game in games),
        "mean_reward": mean(float(game["reward"]) for game in games),
        "errors": sum(game["error"] is not None for game in games),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=ROOT / "main.py")
    parser.add_argument("--opponents", nargs="+", type=Path, required=True)
    parser.add_argument("--seed-start", type=int, default=10_100_000)
    parser.add_argument("--seeds", type=int, default=6)
    parser.add_argument("--workers", type=int, default=32)
    parser.add_argument("--output", type=Path, default=ROOT / "reports/seat_opening_mix.json")
    parser.add_argument("--winner", type=Path, default=ROOT / "candidates/seat_opening_mix/main.py")
    args = parser.parse_args()

    source = args.base.resolve().read_text(encoding="utf-8")
    opponent_paths = {
        (path.parent.name if path.name == "main.py" else path.stem): str(path.resolve())
        for path in args.opponents
    }
    if len(opponent_paths) != len(args.opponents):
        raise SystemExit("opponent names are not unique")

    run_dir = Path(tempfile.mkdtemp(prefix="seat-opening-mix-"))
    try:
        candidate_paths: dict[str, str] = {}
        pairs: dict[str, dict[str, str]] = {}
        for name0, opening0 in OPENINGS.items():
            for name1, opening1 in OPENINGS.items():
                name = f"s0_{name0}__s1_{name1}"
                path = run_dir / f"{name}.py"
                path.write_text(source + wrapper(opening0, opening1), encoding="utf-8")
                candidate_paths[name] = str(path)
                pairs[name] = {"seat0": name0, "seat1": name1}

        seeds = [args.seed_start + 17 * index for index in range(args.seeds)]
        tasks = [
            (candidate, opponent, seed, seat)
            for candidate in candidate_paths
            for opponent in opponent_paths
            for seed in seeds
            for seat in (0, 1)
        ]
        context = mp.get_context("spawn")
        workers = max(1, min(args.workers, os.cpu_count() or args.workers))
        with context.Pool(
            workers, initializer=worker_init, initargs=(candidate_paths, opponent_paths)
        ) as pool:
            games = list(pool.imap_unordered(play, tasks, chunksize=1))

        summaries: dict[str, Any] = {}
        for candidate in candidate_paths:
            selected = [game for game in games if game["candidate"] == candidate]
            by_opponent = {
                opponent: summarize(
                    [game for game in selected if game["opponent"] == opponent]
                )
                for opponent in opponent_paths
            }
            by_seat = {
                str(seat): summarize([game for game in selected if game["seat"] == seat])
                for seat in (0, 1)
            }
            summaries[candidate] = {
                **summarize(selected),
                "by_opponent": by_opponent,
                "by_seat": by_seat,
                "worst_opponent_win_rate": min(row["win_rate"] for row in by_opponent.values()),
                "worst_opponent_margin": min(row["mean_margin"] for row in by_opponent.values()),
                "worst_seat_win_rate": min(row["win_rate"] for row in by_seat.values()),
            }

        ranking = sorted(
            summaries,
            key=lambda name: (
                summaries[name]["errors"] == 0,
                summaries[name]["worst_opponent_win_rate"],
                summaries[name]["worst_opponent_margin"],
                summaries[name]["win_rate"],
                summaries[name]["mean_margin"],
            ),
            reverse=True,
        )
        winner = ranking[0]
        args.winner.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(candidate_paths[winner], args.winner)
        result = {
            "base": str(args.base.resolve()),
            "opponents": opponent_paths,
            "seeds": seeds,
            "openings": OPENINGS,
            "pairs": pairs,
            "ranking": ranking,
            "summaries": summaries,
            "winner": winner,
            "winner_path": str(args.winner.resolve()),
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        for name in ranking[:10]:
            row = summaries[name]
            print(
                f"{name:48} worst_win={row['worst_opponent_win_rate']:.1%} "
                f"worst_margin={row['worst_opponent_margin']:+.1f} "
                f"all_win={row['win_rate']:.1%} mean_margin={row['mean_margin']:+.1f}"
            )
        print(f"winner={winner}")
        print(f"wrote {args.winner}")
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Evaluate one candidate against every test/<name>/main.py opponent."""

from __future__ import annotations

import argparse
import importlib.util
import json
import multiprocessing as mp
import os
from pathlib import Path
from statistics import mean
from typing import Any

# v3 specializes the exact default two-player evaluation path and falls back to
# the stable runner automatically for unsupported configurations.
from production_fast_kaggriculture import run_fast_episode
from agent_runtime import optimize_agent_module
from reference_runtime import optimize_reference_agent_module


ROOT = Path(__file__).resolve().parents[1]
_CANDIDATE_PATH = ""
_OPPONENT_PATHS: dict[str, str] = {}
_FAST_RUNNER = True
_REUSE_AGENTS = True
_OPTIMIZE_AGENT_RUNTIME = True
_CANDIDATE_AGENT: Any = None
_OPPONENT_AGENTS: dict[str, Any] = {}


def load_agent(path: Path, name: str, reference_model: str | None = None) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if _OPTIMIZE_AGENT_RUNTIME:
        if reference_model is None:
            optimize_agent_module(module)
        else:
            optimize_reference_agent_module(module, reference_model)
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
    if not available:
        raise SystemExit(f"no models found below {models_dir}")
    return available


def worker_init(candidate: str, opponents: dict[str, str], fast_runner: bool,
                reuse_agents: bool, optimize_agent_runtime: bool) -> None:
    global _CANDIDATE_PATH, _OPPONENT_PATHS, _FAST_RUNNER, _REUSE_AGENTS
    global _CANDIDATE_AGENT, _OPPONENT_AGENTS, _OPTIMIZE_AGENT_RUNTIME
    _CANDIDATE_PATH = candidate
    _OPPONENT_PATHS = opponents
    _FAST_RUNNER = fast_runner
    _REUSE_AGENTS = reuse_agents
    _OPTIMIZE_AGENT_RUNTIME = optimize_agent_runtime
    _CANDIDATE_AGENT = None
    _OPPONENT_AGENTS = {}


def game_agents(name: str, suffix: str) -> tuple[Any, Any]:
    global _CANDIDATE_AGENT
    if not _REUSE_AGENTS:
        return (
            load_agent(Path(_CANDIDATE_PATH), f"test_candidate_{suffix}"),
            load_agent(
                Path(_OPPONENT_PATHS[name]),
                f"test_opponent_{suffix}",
                reference_model=name,
            ),
        )
    # Competition agents reset their per-player state when observation.step
    # returns to zero. Search already relies on this contract; retaining one
    # module per worker avoids recompiling large public agents every episode.
    if _CANDIDATE_AGENT is None:
        _CANDIDATE_AGENT = load_agent(
            Path(_CANDIDATE_PATH), f"test_candidate_{os.getpid()}"
        )
    opponent = _OPPONENT_AGENTS.get(name)
    if opponent is None:
        opponent = load_agent(
            Path(_OPPONENT_PATHS[name]),
            f"test_opponent_{os.getpid()}_{name}",
            reference_model=name,
        )
        _OPPONENT_AGENTS[name] = opponent
    return _CANDIDATE_AGENT, opponent


def play(task: tuple[str, int, int]) -> dict[str, Any]:
    name, seed, seat = task
    try:
        suffix = f"{os.getpid()}_{name}_{seed}_{seat}"
        candidate, opponent = game_agents(name, suffix)
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
            "model": name,
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
            "model": name,
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


def summarize(games: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "games": len(games),
        "wins": sum(bool(game["win"]) for game in games),
        "ties": sum(bool(game["tie"]) for game in games),
        "win_rate": mean(float(bool(game["win"])) for game in games),
        "mean_reward": mean(float(game["reward"]) for game in games),
        "mean_opponent_reward": mean(float(game["opponent_reward"]) for game in games),
        "mean_margin": mean(float(game["margin"]) for game in games),
        "errors": sum(game["error"] is not None for game in games),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, default=ROOT / "main.py")
    parser.add_argument("--models-dir", type=Path, default=ROOT / "test")
    parser.add_argument("--models", nargs="*", default=[])
    parser.add_argument("--seed-start", type=int, default=9_700_000)
    parser.add_argument("--seeds", type=int, default=100)
    parser.add_argument("--workers", type=int, default=20)
    parser.add_argument(
        "--fast-runner", action=argparse.BooleanOptionalAction, default=True
    )
    parser.add_argument(
        "--reuse-agents", action=argparse.BooleanOptionalAction, default=True,
        help="reuse loaded modules within each worker; agents reset at step zero",
    )
    parser.add_argument(
        "--optimize-agent-runtime", action=argparse.BooleanOptionalAction,
        default=True, help="use runtime-only Python/C++ hot-path accelerators",
    )
    parser.add_argument("--output", type=Path, default=ROOT / "reports/test_models.json")
    args = parser.parse_args()

    opponents = discover(args.models_dir.resolve(), args.models)
    seeds = [args.seed_start + index * 17 for index in range(args.seeds)]
    tasks = [
        (name, seed, seat)
        for name in opponents
        for seed in seeds
        for seat in (0, 1)
    ]
    context = mp.get_context("spawn")
    workers = max(1, min(args.workers, os.cpu_count() or args.workers))
    with context.Pool(
        workers,
        initializer=worker_init,
        initargs=(
            str(args.candidate.resolve()),
            {name: str(path) for name, path in opponents.items()},
            args.fast_runner,
            args.reuse_agents,
            args.optimize_agent_runtime,
        ),
    ) as pool:
        games = list(pool.imap_unordered(play, tasks, chunksize=1))

    games.sort(key=lambda game: (game["model"], game["seed"], game["seat"]))
    summaries = {
        name: summarize([game for game in games if game["model"] == name])
        for name in opponents
    }
    result = {
        "candidate": str(args.candidate.resolve()),
        "models_dir": str(args.models_dir.resolve()),
        "fast_runner": args.fast_runner,
        "reuse_agents": args.reuse_agents,
        "optimize_agent_runtime": args.optimize_agent_runtime,
        "models": {name: str(path) for name, path in opponents.items()},
        "summaries": summaries,
        "games": games,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    for name, summary in summaries.items():
        print(
            f"{name:28} wins={summary['wins']}/{summary['games']} "
            f"rate={summary['win_rate']:.1%} margin={summary['mean_margin']:+.1f} "
            f"reward={summary['mean_reward']:.1f} errors={summary['errors']}"
        )
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()

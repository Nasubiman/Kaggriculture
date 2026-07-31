#!/usr/bin/env python3
"""Evaluate a learned counterfactual macro-profile selector in Arena games."""

from __future__ import annotations

import argparse
import importlib.util
import json
import multiprocessing as mp
import os
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any

import numpy as np
import torch

from counterfactual_value import load_value_checkpoint
from fast_kaggriculture import run_fast_episode
from generate_macro_counterfactuals import PROFILES, state_features


ROOT = Path(__file__).resolve().parents[1]
_CHECKPOINT_CACHE: dict[str, tuple[Any, dict[str, Any]]] = {}


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def cached_checkpoint(path: str) -> tuple[Any, dict[str, Any]]:
    cached = _CHECKPOINT_CACHE.get(path)
    if cached is None:
        cached = load_value_checkpoint(Path(path), "cpu")
        _CHECKPOINT_CACHE[path] = cached
    return cached


class ValueProfileAgent:
    def __init__(self, module: Any, checkpoint: str, decision_day: int):
        self.module = module
        self.model, self.payload = cached_checkpoint(checkpoint)
        self.decision_day = decision_day
        self.applied = False
        self.selected_profile = "KEEP"

    def __call__(self, obs: dict[str, Any]) -> dict[str, Any]:
        if not self.applied and int(obs.get("day", 0)) >= self.decision_day:
            features = state_features(obs)
            values = np.asarray(
                [float(features[name]) for name in self.payload["feature_names"]],
                dtype=np.float32,
            )
            values = (
                values - np.asarray(self.payload["feature_mean"], dtype=np.float32)
            ) / np.asarray(self.payload["feature_scale"], dtype=np.float32)
            with torch.no_grad():
                prediction = self.model(torch.from_numpy(values).unsqueeze(0))[0]
            index = int(prediction.argmax())
            self.selected_profile = str(self.payload["profile_names"][index])
            learned_profile = getattr(
                self.module, "_apply_learned_macro_profile", None
            )
            if learned_profile is not None:
                learned_profile(obs)
                self.module._apply_learned_macro_profile = lambda _obs: None
            for name, value in PROFILES[self.selected_profile].items():
                setattr(self.module, name, value)
            self.applied = True
        return self.module.agent(obs)


def play(task: dict[str, Any]) -> dict[str, Any]:
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")
    torch.set_num_threads(1)
    seed = int(task["seed"])
    seat = int(task["seat"])
    suffix = f"{os.getpid()}_{seed}_{seat}"
    candidate_module = load_module(Path(task["agent"]), f"value_{suffix}")
    opponent_module = load_module(Path(task["opponent"]), f"opponent_{suffix}")
    candidate = ValueProfileAgent(
        candidate_module, task["checkpoint"], int(task["decision_day"])
    )
    def candidate_function(obs: dict[str, Any]) -> dict[str, Any]:
        return candidate(obs)

    agents = (
        [candidate_function, opponent_module.agent]
        if seat == 0
        else [opponent_module.agent, candidate_function]
    )
    if bool(task["fast_runner"]):
        final = run_fast_episode(agents, seed=seed)
    else:
        from kaggle_environments import make

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
        "seed": seed,
        "seat": seat,
        "profile": candidate.selected_profile,
        "reward": reward,
        "opponent_reward": opponent_reward,
        "margin": reward - opponent_reward,
        "win": reward > opponent_reward,
        "tie": reward == opponent_reward,
        "status": str(final[seat].status),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--agent", type=Path, default=ROOT / "main.py")
    parser.add_argument("--opponent", type=Path, default=ROOT / "main.py")
    parser.add_argument("--decision-day", type=int, default=8)
    parser.add_argument("--seed-start", type=int, default=900_000)
    parser.add_argument("--seeds", type=int, default=100)
    parser.add_argument("--workers", type=int, default=20)
    parser.add_argument(
        "--fast-runner",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    tasks = [
        {
            "checkpoint": str(args.checkpoint.resolve()),
            "agent": str(args.agent.resolve()),
            "opponent": str(args.opponent.resolve()),
            "decision_day": args.decision_day,
            "seed": args.seed_start + index * 17,
            "seat": seat,
            "fast_runner": args.fast_runner,
        }
        for index in range(args.seeds)
        for seat in (0, 1)
    ]
    context = mp.get_context("spawn")
    with context.Pool(max(1, min(args.workers, os.cpu_count() or args.workers))) as pool:
        games = list(pool.imap_unordered(play, tasks, chunksize=1))
    profile_counts = Counter(game["profile"] for game in games)
    result = {
        "checkpoint": str(args.checkpoint.resolve()),
        "fast_runner": args.fast_runner,
        "games": sorted(games, key=lambda game: (game["seed"], game["seat"])),
        "summary": {
            "games": len(games),
            "wins": sum(game["win"] for game in games),
            "ties": sum(game["tie"] for game in games),
            "win_rate": mean(float(game["win"]) for game in games),
            "mean_reward": mean(game["reward"] for game in games),
            "mean_margin": mean(game["margin"] for game in games),
            "selected_profiles": dict(sorted(profile_counts.items())),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2))
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()

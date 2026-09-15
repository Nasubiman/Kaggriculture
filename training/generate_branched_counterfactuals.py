#!/usr/bin/env python3
"""Generate multi-day macro counterfactuals from shared episode prefixes."""

from __future__ import annotations

import argparse
import importlib.util
import json
import multiprocessing as mp
import os
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

from production_fast_kaggriculture import (
    clone_fast_state,
    create_fast_episode,
    run_fast_steps,
)
from generate_macro_counterfactuals import PROFILES, ProfileAgent, state_features
from hybrid_policy import load_pasted_agent


ROOT = Path(__file__).resolve().parents[1]
MACRO_NAMES = (
    "COW_START_DAY",
    "COW_TARGET",
    "COW_PURCHASE_BATCH",
    "COW_HANDS",
    "WHEAT_TILES",
    "WHEAT_PICKUP_BATCH",
    "SALE_PROCEEDS_FACTOR",
    "SHEEP_TARGET",
)
DEFAULT_PROFILES = (
    "KEEP",
    "COW_14",
    "COW_15",
    "COW_17",
    "SHEEP_2",
    "SHEEP_3",
    "SHEEP_5",
    "HANDS_10",
    "HANDS_12",
    "WHEAT_2",
    "WHEAT_4",
    "BATCH_6",
    "BATCH_8",
)


def load_module(path: Path, name: str) -> Any:
    if path.suffix != ".py":
        return load_pasted_agent(path)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def macro_state(module: Any) -> dict[str, Any]:
    return {
        name: getattr(module, name)
        for name in MACRO_NAMES
        if hasattr(module, name)
    }


def restore_macro_state(module: Any, values: dict[str, Any]) -> None:
    for name, value in values.items():
        setattr(module, name, value)


def generate_seed(task: dict[str, Any]) -> list[dict[str, Any]]:
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")
    seed = int(task["seed"])
    decision_days = list(task["decision_days"])
    profiles = list(task["profiles"])
    agent_path = Path(task["agent"])
    opponent_path = Path(task["opponent"])
    prefix_modules = [
        load_module(agent_path, f"prefix_a_{os.getpid()}_{seed}"),
        load_module(opponent_path, f"prefix_b_{os.getpid()}_{seed}"),
    ]
    prefix_agents = [module.agent for module in prefix_modules]
    env, live_state = create_fast_episode(seed=seed, num_agents=2)
    snapshots: dict[int, tuple[list[Any], list[dict[str, Any]]]] = {}
    for day in decision_days:
        live_state = run_fast_steps(
            prefix_agents,
            env=env,
            state=live_state,
            stop_step=day * 24,
        )
        snapshots[day] = (
            clone_fast_state(live_state),
            [macro_state(module) for module in prefix_modules],
        )

    contexts = []
    for day in decision_days:
        snapshot, player_macros = snapshots[day]
        for seat in (0, 1):
            features = state_features(snapshot[seat].observation)
            outcomes = {}
            for profile_name in profiles:
                suffix = f"{os.getpid()}_{seed}_{day}_{seat}_{profile_name}"
                candidate_module = load_module(agent_path, f"branch_c_{suffix}")
                opponent_module = load_module(opponent_path, f"branch_o_{suffix}")
                restore_macro_state(candidate_module, player_macros[seat])
                restore_macro_state(opponent_module, player_macros[1 - seat])
                candidate = ProfileAgent(
                    candidate_module, PROFILES[profile_name], day
                )

                def candidate_function(obs: dict[str, Any]) -> dict[str, Any]:
                    return candidate(obs)

                agents = (
                    [candidate_function, opponent_module.agent]
                    if seat == 0
                    else [opponent_module.agent, candidate_function]
                )
                final = run_fast_steps(
                    agents,
                    env=env,
                    state=clone_fast_state(snapshot),
                    stop_step=719,
                )
                reward = float(final[seat].reward)
                opponent_reward = float(final[1 - seat].reward)
                outcomes[profile_name] = {
                    "reward": reward,
                    "opponent_reward": opponent_reward,
                    "margin": reward - opponent_reward,
                    "win": reward > opponent_reward,
                    "tie": reward == opponent_reward,
                    "status": str(final[seat].status),
                }
            contexts.append(
                {
                    "seed": seed,
                    "seat": seat,
                    "decision_day": day,
                    "features": features,
                    "outcomes": outcomes,
                }
            )
    return contexts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", type=Path, default=ROOT / "main.py")
    parser.add_argument("--opponent", type=Path, default=ROOT / "main.py")
    parser.add_argument("--decision-days", type=int, nargs="+", default=[8, 12, 16, 20, 24])
    parser.add_argument("--seed-start", type=int, default=1_300_000)
    parser.add_argument("--seeds", type=int, default=200)
    parser.add_argument("--workers", type=int, default=20)
    parser.add_argument("--profiles", nargs="+", choices=sorted(PROFILES), default=list(DEFAULT_PROFILES))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.opponent.suffix != ".py":
        raise RuntimeError(
            "Branched continuation cannot restore arbitrary stateful opponent "
            "internals; use generate_macro_counterfactuals.py instead."
        )
    decision_days = sorted(set(args.decision_days))
    if not decision_days or decision_days[0] < 1 or decision_days[-1] >= 30:
        raise RuntimeError("decision days must be between 1 and 29")
    tasks = [
        {
            "seed": args.seed_start + index * 17,
            "decision_days": decision_days,
            "profiles": args.profiles,
            "agent": str(args.agent.resolve()),
            "opponent": str(args.opponent.resolve()),
        }
        for index in range(args.seeds)
    ]
    context = mp.get_context("spawn")
    all_contexts = []
    with context.Pool(max(1, min(args.workers, os.cpu_count() or args.workers))) as pool:
        for index, contexts in enumerate(
            pool.imap_unordered(generate_seed, tasks, chunksize=1), start=1
        ):
            all_contexts.extend(contexts)
            if index % 10 == 0 or index == len(tasks):
                branches = len(all_contexts) * len(args.profiles)
                print(
                    f"completed seeds={index}/{len(tasks)} "
                    f"contexts={len(all_contexts)} branches={branches}",
                    flush=True,
                )

    by_profile: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in all_contexts:
        for profile, outcome in item["outcomes"].items():
            by_profile[profile].append(outcome)
    summary = {
        profile: {
            "branches": len(outcomes),
            "win_rate": mean(float(item["win"]) for item in outcomes),
            "mean_margin": mean(float(item["margin"]) for item in outcomes),
        }
        for profile, outcomes in by_profile.items()
    }
    result = {
        "format": "branched_counterfactual_v1",
        "agent": str(args.agent.resolve()),
        "opponent": str(args.opponent.resolve()),
        "decision_days": decision_days,
        "profiles": {name: PROFILES[name] for name in args.profiles},
        "seeds": [task["seed"] for task in tasks],
        "summary": summary,
        "contexts": sorted(
            all_contexts,
            key=lambda item: (item["seed"], item["decision_day"], item["seat"]),
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()

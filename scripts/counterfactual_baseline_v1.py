#!/usr/bin/env python3
"""Counterfactual local mutations for the archived baseline_v1 policy."""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
from pathlib import Path
from statistics import mean

from kaggle_environments import make

from head_to_head import DEFAULT_REFERENCE, load_pasted_agent


ROOT = Path(__file__).resolve().parents[1]


def load_agent(path: Path):
    spec = importlib.util.spec_from_file_location("baseline_v1", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.agent


def mutated(base_agent, mutation: str):
    def agent(obs):
        action = copy.deepcopy(base_agent(obs))
        day = int(obs.get("day", 0))
        hour = int(obs.get("hour", 0))
        farm = obs["farms"][int(obs.get("player", 0))]

        if mutation == "seeds_before_hires" and day == 0 and hour == 0:
            action["market"] = [
                ["BUY_SEED", "WHEAT", 12],
                ["BUY_SEED", "CARROT", 10],
                ["BUY_SEED", "MELON", 3],
            ]
        elif mutation == "reference_mix_before_hires" and day == 0 and hour == 0:
            action["market"] = [
                ["BUY_SEED", "MELON", 13],
                ["BUY_SEED", "CARROT", 4],
                ["BUY_SEED", "WHEAT", 4],
                ["BUY_SEED", "TOMATO", 2],
                ["BUY_SEED", "STRAWBERRY", 2],
            ]
        elif mutation.startswith("cap_hires_"):
            cap = int(mutation.rsplit("_", 1)[1])
            hires = int(farm.get("hires_today", 0))
            filtered = []
            for order in action.get("market", []):
                if order and order[0] == "HIRE":
                    if hires >= cap:
                        continue
                    hires += 1
                filtered.append(order)
            action["market"] = filtered
        elif mutation == "delay_land_to_day_11" and day < 11:
            action["market"] = [
                order
                for order in action.get("market", [])
                if not order or order[0] != "BUY_LAND"
            ]
        elif mutation == "reverse_market_order":
            action["market"] = list(reversed(action.get("market", [])))
        elif mutation.startswith("reverse_step_"):
            target_step = int(mutation.rsplit("_", 1)[1])
            if int(obs.get("step", -1)) == target_step:
                action["market"] = list(reversed(action.get("market", [])))
        return action

    return agent


def play(candidate, opponent, seed: int, seat: int) -> tuple[float, float]:
    agents = [candidate, opponent] if seat == 0 else [opponent, candidate]
    env = make(
        "kaggriculture",
        configuration={"episodeSteps": 720, "seed": seed},
        debug=True,
    )
    env.run(agents)
    final = env.steps[-1]
    return float(final[seat].reward), float(final[1 - seat].reward)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", nargs="+", type=int, default=[101])
    parser.add_argument("--mutations", nargs="+")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "reports" / "baseline_v1_counterfactuals.json",
    )
    args = parser.parse_args()
    base = load_agent(ROOT / "agents" / "baseline_v1.py")
    opponent = load_pasted_agent(DEFAULT_REFERENCE)
    mutations = [
        "none",
        "seeds_before_hires",
        "reference_mix_before_hires",
        "cap_hires_6",
        "cap_hires_7",
        "cap_hires_8",
        "cap_hires_9",
        "delay_land_to_day_11",
        "reverse_market_order",
    ]
    if args.mutations:
        mutations = args.mutations
    results = []
    for mutation in mutations:
        candidate = base if mutation == "none" else mutated(base, mutation)
        games = [
            play(candidate, opponent, seed, seat)
            for seed in args.seeds
            for seat in (0, 1)
        ]
        result = {
            "mutation": mutation,
            "mean_reward": mean(reward for reward, _ in games),
            "mean_opponent": mean(reward for _, reward in games),
            "mean_margin": mean(
                reward - opponent_reward
                for reward, opponent_reward in games
            ),
            "games": games,
        }
        results.append(result)
        print(
            f"{mutation}: reward={result['mean_reward']:.1f}, "
            f"margin={result['mean_margin']:+.1f}"
        )
    results.sort(key=lambda result: result["mean_reward"], reverse=True)
    output = args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print("BEST", json.dumps(results[0], indent=2))
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()

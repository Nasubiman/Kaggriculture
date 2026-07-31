#!/usr/bin/env python3
"""Evaluate one-shot macro profiles against the incumbent in parallel."""

from __future__ import annotations

import argparse
import importlib.util
import json
import multiprocessing as mp
import os
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

from hybrid_policy import load_pasted_agent


ROOT = Path(__file__).resolve().parents[1]
PRODUCTS = (
    "WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON",
    "EGG", "MILK", "WOOL", "FERTILIZER",
)
BASE = {
    "COW_START_DAY": 8,
    "COW_TARGET": 16,
    "COW_PURCHASE_BATCH": 4,
    "COW_HANDS": 11,
    "WHEAT_TILES": 3,
    "WHEAT_PICKUP_BATCH": 12,
    "SHEEP_TARGET": 4,
}
PROFILES: dict[str, dict[str, int]] = {
    "KEEP": {},
    "COW_14": {"COW_TARGET": 14},
    "COW_15": {"COW_TARGET": 15},
    "COW_17": {"COW_TARGET": 17},
    "COW_18": {"COW_TARGET": 18},
    "SHEEP_2": {"SHEEP_TARGET": 2},
    "SHEEP_3": {"SHEEP_TARGET": 3},
    "SHEEP_5": {"SHEEP_TARGET": 5},
    "SHEEP_6": {"SHEEP_TARGET": 6},
    "HANDS_10": {"COW_HANDS": 10},
    "HANDS_12": {"COW_HANDS": 12},
    "WHEAT_2": {"WHEAT_TILES": 2},
    "WHEAT_4": {"WHEAT_TILES": 4},
    "BATCH_6": {"COW_PURCHASE_BATCH": 6},
    "BATCH_8": {"COW_PURCHASE_BATCH": 8},
    "DELAY_9": {"COW_START_DAY": 9},
    "DELAY_10": {"COW_START_DAY": 10},
    "C15_W2": {"COW_TARGET": 15, "WHEAT_TILES": 2},
    "C15_S5": {"COW_TARGET": 15, "SHEEP_TARGET": 5},
    "C17_S3": {"COW_TARGET": 17, "SHEEP_TARGET": 3},
    "C17_S5_H12": {
        "COW_TARGET": 17, "SHEEP_TARGET": 5, "COW_HANDS": 12,
    },
    "C18_S2_H12": {
        "COW_TARGET": 18, "SHEEP_TARGET": 2, "COW_HANDS": 12,
    },
    "C14_S6": {"COW_TARGET": 14, "SHEEP_TARGET": 6},
}


def load_module(path: Path, name: str) -> Any:
    if path.suffix != ".py":
        return load_pasted_agent(path)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def farm_counts(farm: dict[str, Any]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for row in farm.get("tiles", []):
        for tile in row:
            if not isinstance(tile, dict):
                continue
            if tile.get("crop"):
                counts[str(tile["crop"])] += 1
            if tile.get("animal"):
                counts[str(tile["animal"])] += 1
    return counts


def state_features(obs: dict[str, Any]) -> dict[str, float]:
    player = int(obs.get("player", 0))
    farms = obs.get("farms", []) or []
    opponent = 1 - player
    own_farm = farms[player]
    opponent_farm = farms[opponent]
    own = farm_counts(own_farm)
    other = farm_counts(opponent_farm)
    market = obs.get("market", {}) or {}
    prices = market.get("prices", {}) or {}
    inventory = market.get("inventory", {}) or {}
    features = {
        "day": float(obs.get("day", 0)),
        "hour": float(obs.get("hour", 0)),
        "own_money": float(own_farm.get("money", 0)),
        "opponent_money": float(opponent_farm.get("money", 0)),
        "own_hands": float(len(own_farm.get("hands", []))),
        "opponent_hands": float(len(opponent_farm.get("hands", []))),
        "shops": float(
            len((obs.get("town", {}) or {}).get("unlocked_shops", []) or [])
        ),
    }
    for item in ("COW", "SHEEP", "MELON", "CARROT", "WHEAT"):
        features[f"own_{item.lower()}"] = float(own[item])
        features[f"opponent_{item.lower()}"] = float(other[item])
    for product in PRODUCTS:
        features[f"price_{product.lower()}"] = float(prices.get(product, 0))
        features[f"inventory_{product.lower()}"] = float(
            inventory.get(product, 10_000)
        )
    features["milk_minus_wool"] = (
        features["price_milk"] - features["price_wool"]
    )
    return features


class ProfileAgent:
    def __init__(self, module: Any, profile: dict[str, int], decision_day: int):
        self.module = module
        self.profile = profile
        self.decision_day = decision_day
        self.applied = False
        self.features: dict[str, float] | None = None

    def __call__(self, obs: dict[str, Any]) -> dict[str, Any]:
        day = int(obs.get("day", 0))
        if not self.applied and day >= self.decision_day:
            self.features = state_features(obs)
            # main.py has its own day-8 learned default. Resolve that first,
            # then disable the hook so this explicit counterfactual profile is
            # the final decision rather than being silently overwritten.
            learned_profile = getattr(
                self.module, "_apply_learned_macro_profile", None
            )
            if learned_profile is not None:
                learned_profile(obs)
                self.module._apply_learned_macro_profile = lambda _obs: None
            for name, value in self.profile.items():
                setattr(self.module, name, value)
            self.applied = True
        return self.module.agent(obs)


def play(
    task: tuple[str, int, int, int, str, str, bool]
) -> dict[str, Any]:
    (
        profile_name,
        seed,
        seat,
        decision_day,
        agent_path,
        incumbent_path,
        fast_runner,
    ) = task
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")
    from kaggle_environments import make

    suffix = f"{os.getpid()}_{profile_name}_{seed}_{seat}"
    candidate_module = load_module(Path(agent_path), f"candidate_{suffix}")
    incumbent_module = load_module(
        Path(incumbent_path), f"incumbent_{suffix}"
    )
    candidate = ProfileAgent(
        candidate_module, PROFILES[profile_name], decision_day
    )

    def candidate_function(obs: dict[str, Any]) -> dict[str, Any]:
        return candidate(obs)

    agents = (
        [candidate_function, incumbent_module.agent]
        if seat == 0
        else [incumbent_module.agent, candidate_function]
    )
    if fast_runner:
        from fast_kaggriculture import run_fast_episode

        final = run_fast_episode(agents, seed=seed)
    else:
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
        "profile": profile_name,
        "seed": seed,
        "seat": seat,
        "decision_day": decision_day,
        "reward": reward,
        "opponent_reward": opponent_reward,
        "margin": reward - opponent_reward,
        "win": reward > opponent_reward,
        "tie": reward == opponent_reward,
        "status": str(final[seat].status),
        "features": candidate.features,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", type=Path, default=ROOT / "main.py")
    parser.add_argument(
        "--incumbent-agent",
        type=Path,
        help="Opponent agent; defaults to the candidate agent.",
    )
    parser.add_argument("--decision-day", type=int, default=8)
    parser.add_argument("--seed-start", type=int, default=500_000)
    parser.add_argument("--seeds", type=int, default=40)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument(
        "--fast-runner",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use the official interpreter without generic runner overhead.",
    )
    parser.add_argument(
        "--profiles", nargs="+", choices=sorted(PROFILES), default=list(PROFILES)
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    seed_values = [
        args.seed_start + index * 17
        for index in range(args.seeds)
    ]
    incumbent_agent = (args.incumbent_agent or args.agent).resolve()
    tasks = [
        (
            profile,
            seed,
            seat,
            args.decision_day,
            str(args.agent.resolve()),
            str(incumbent_agent),
            args.fast_runner,
        )
        for profile in args.profiles
        for seed in seed_values
        for seat in (0, 1)
    ]
    context = mp.get_context("spawn")
    games = []
    with context.Pool(max(1, min(args.workers, os.cpu_count() or args.workers))) as pool:
        for index, game in enumerate(
            pool.imap_unordered(play, tasks, chunksize=1), start=1
        ):
            games.append(game)
            if index % 100 == 0 or index == len(tasks):
                print(f"completed {index}/{len(tasks)}", flush=True)

    by_profile: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for game in games:
        by_profile[game["profile"]].append(game)
    summary = {}
    for profile, subset in by_profile.items():
        summary[profile] = {
            "games": len(subset),
            "wins": sum(game["win"] for game in subset),
            "ties": sum(game["tie"] for game in subset),
            "win_rate": mean(float(game["win"]) for game in subset),
            "mean_reward": mean(game["reward"] for game in subset),
            "mean_margin": mean(game["margin"] for game in subset),
        }
    result = {
        "agent": str(args.agent.resolve()),
        "incumbent_agent": str(incumbent_agent),
        "decision_day": args.decision_day,
        "fast_runner": args.fast_runner,
        "seeds": seed_values,
        "profiles": {name: PROFILES[name] for name in args.profiles},
        "summary": dict(
            sorted(
                summary.items(),
                key=lambda item: (
                    item[1]["win_rate"], item[1]["mean_margin"]
                ),
                reverse=True,
            )
        ),
        "games": sorted(
            games,
            key=lambda game: (game["seed"], game["seat"], game["profile"]),
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2), flush=True)
    print(f"wrote {args.output}", flush=True)


if __name__ == "__main__":
    main()

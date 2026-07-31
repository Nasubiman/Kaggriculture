#!/usr/bin/env python3
"""Search small cow-strategy parameter variations against the crop agent."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from statistics import mean

from kaggle_environments import make


ROOT = Path(__file__).resolve().parents[1]


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def play(candidate, reference, seed: int, seat: int) -> tuple[float, float]:
    agents = (
        [candidate, reference]
        if seat == 0
        else [reference, candidate]
    )
    env = make(
        "kaggriculture",
        configuration={"episodeSteps": 720, "seed": seed},
        debug=False,
    )
    env.run(agents)
    final = env.steps[-1]
    return (
        float(final[seat].reward),
        float(final[1 - seat].reward),
    )


def main() -> None:
    candidate_module = load_module(
        ROOT / "main.py",
        "cow_variant_candidate",
    )
    reference_module = load_module(
        ROOT / "agents" / "pulse_breaker_v2.py",
        "cow_variant_reference",
    )
    variants = [
        ("start10_cow22_s4", 10, 22, 4, 12, 0.65),
        ("start9_cow22_s2", 9, 22, 2, 12, 0.65),
        ("start11_cow20_s2", 11, 20, 2, 12, 0.65),
        ("start11_cow20_s0", 11, 20, 0, 12, 0.65),
    ]
    seeds = [303, 404, 505]
    results = []
    for (
        name,
        start_day,
        cow_target,
        sheep_target,
        hands,
        sale_factor,
    ) in variants:
        candidate_module.COW_START_DAY = start_day
        candidate_module.COW_TARGET = cow_target
        candidate_module.SHEEP_TARGET = sheep_target
        candidate_module.COW_HANDS = hands
        candidate_module.SALE_PROCEEDS_FACTOR = sale_factor
        games = [
            play(
                candidate_module.agent,
                reference_module.agent,
                seed,
                seat,
            )
            for seed in seeds
            for seat in (0, 1)
        ]
        result = {
            "name": name,
            "start_day": start_day,
            "cow_target": cow_target,
            "sheep_target": sheep_target,
            "hands": hands,
            "sale_factor": sale_factor,
            "mean_reward": mean(score for score, _ in games),
            "mean_opponent": mean(score for _, score in games),
            "mean_margin": mean(
                score - opponent for score, opponent in games
            ),
            "wins": sum(score > opponent for score, opponent in games),
            "games": len(games),
        }
        results.append(result)
        print(
            f"{name}: reward={result['mean_reward']:.1f}, "
            f"margin={result['mean_margin']:+.1f}, "
            f"wins={result['wins']}/{result['games']}"
        )

    results.sort(key=lambda result: result["mean_reward"], reverse=True)
    output = ROOT / "reports" / "cow_variant_search.json"
    output.write_text(
        json.dumps(results, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()

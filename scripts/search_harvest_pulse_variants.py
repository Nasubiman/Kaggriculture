#!/usr/bin/env python3
"""Screen parameter variants of the user-provided Harvest Pulse agent."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean

from kaggle_environments import make

from head_to_head import DEFAULT_REFERENCE


def reference_source(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    source = text.split("%%writefile /kaggle/working/main.py", 1)[1]
    source = source.rsplit("Writing /kaggle/working/main.py", 1)[0]
    return source.replace(
        "min(amount, 2)",
        "min(amount, MELON_CLIP)",
    )


def make_agent(source: str, variant: dict):
    namespace = {"MELON_CLIP": variant.get("melon_clip", 2)}
    exec(compile(source, "<harvest-pulse-variant>", "exec"), namespace)
    for key, value in variant.items():
        if key != "name" and key != "melon_clip":
            namespace[key] = value
    return namespace["agent"]


def play(candidate, reference, seed: int, seat: int) -> tuple[float, float]:
    agents = [candidate, reference] if seat == 0 else [reference, candidate]
    env = make(
        "kaggriculture",
        configuration={"episodeSteps": 720, "seed": seed},
        debug=True,
    )
    env.run(agents)
    final = env.steps[-1]
    return float(final[seat].reward), float(final[1 - seat].reward)


def variants() -> list[dict]:
    reference_mix = (
        ("MELON", 13),
        ("CARROT", 4),
        ("WHEAT", 4),
        ("TOMATO", 2),
        ("STRAWBERRY", 2),
    )
    mixes = {
        "reference": reference_mix,
        "less_melon": (
            ("MELON", 10),
            ("CARROT", 5),
            ("WHEAT", 6),
            ("TOMATO", 2),
            ("STRAWBERRY", 2),
        ),
        "balanced": (
            ("MELON", 8),
            ("CARROT", 5),
            ("WHEAT", 7),
            ("TOMATO", 2),
            ("STRAWBERRY", 3),
        ),
        "wheat_heavy": (
            ("MELON", 5),
            ("CARROT", 4),
            ("WHEAT", 11),
            ("TOMATO", 2),
            ("STRAWBERRY", 3),
        ),
        "melon_heavy": (
            ("MELON", 16),
            ("CARROT", 3),
            ("WHEAT", 3),
            ("TOMATO", 1),
            ("STRAWBERRY", 2),
        ),
    }
    result = []
    for mix_name, mix in mixes.items():
        for hands in (6, 7, 8, 9):
            result.append(
                {
                    "name": f"{mix_name}_h{hands}",
                    "MIX": mix,
                    "TARGET_HANDS": hands,
                    "EXTRA_WHEAT": 15,
                    "LAND_DAY": 11,
                    "melon_clip": 2,
                }
            )
    for clip in (1, 3, 5, 999):
        result.append(
            {
                "name": f"reference_clip{clip}",
                "MIX": reference_mix,
                "TARGET_HANDS": 7,
                "EXTRA_WHEAT": 15,
                "LAND_DAY": 11,
                "melon_clip": clip,
            }
        )
    for land_day, extra_wheat in ((9, 20), (10, 20), (11, 20), (12, 20), (11, 25)):
        result.append(
            {
                "name": f"reference_land{land_day}_w{extra_wheat}",
                "MIX": reference_mix,
                "TARGET_HANDS": 7,
                "EXTRA_WHEAT": extra_wheat,
                "LAND_DAY": land_day,
                "melon_clip": 2,
            }
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--seeds", nargs="+", type=int, default=[701])
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--stop", type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    source = reference_source(args.reference)
    baseline = make_agent(source, {"name": "reference", "melon_clip": 2})
    selected = variants()[args.start : args.stop]
    results = []
    for index, variant in enumerate(selected, start=args.start):
        candidate = make_agent(source, variant)
        games = [
            play(candidate, baseline, seed, seat)
            for seed in args.seeds
            for seat in (0, 1)
        ]
        result = {
            "index": index,
            "name": variant["name"],
            "wins": sum(candidate_reward > reference_reward for candidate_reward, reference_reward in games),
            "games": len(games),
            "mean_reward": mean(candidate_reward for candidate_reward, _ in games),
            "mean_opponent": mean(reference_reward for _, reference_reward in games),
            "mean_margin": mean(candidate_reward - reference_reward for candidate_reward, reference_reward in games),
            "variant": variant,
        }
        results.append(result)
        print(
            f"{index:02d} {result['name']}: {result['wins']}/{result['games']} "
            f"margin={result['mean_margin']:+.0f}"
        )
    results.sort(key=lambda item: (item["wins"], item["mean_margin"]), reverse=True)
    print("TOP", json.dumps(results[:5], indent=2))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

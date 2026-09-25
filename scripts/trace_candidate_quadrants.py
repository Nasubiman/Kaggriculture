#!/usr/bin/env python3
"""Trace an agent's expansion and southeast field in the fast simulator."""

from __future__ import annotations

import argparse
from collections import Counter
import importlib.util
from pathlib import Path

from kaggle_environments.agent import get_last_callable
from production_fast_kaggriculture import create_fast_episode, run_fast_steps


def load(path: Path, module: bool):
    if not module:
        return get_last_callable(path.read_text(), path=str(path))
    spec = importlib.util.spec_from_file_location(f"trace_{path.parent.name}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return getattr(loaded, "agent", None) or getattr(loaded, "kaggle_agent")


def summary(state, seat: int) -> dict:
    obs = state[seat].observation
    farm = obs["farms"][seat]
    se = Counter()
    by_quadrant = {name: Counter() for name in ("NW", "NE", "SW", "SE")}
    for row in farm["tiles"][5:10]:
        for tile in row[5:10]:
            if not isinstance(tile, dict):
                continue
            label = tile["kind"]
            if label == "PLANT":
                label += ":" + tile["crop"]
            elif label == "PASTURE":
                label += ":" + str(tile.get("animal"))
            se[label] += 1
    for y, row in enumerate(farm["tiles"]):
        for x, tile in enumerate(row):
            if not isinstance(tile, dict):
                continue
            quadrant = ("N" if y < 5 else "S") + ("W" if x < 5 else "E")
            if tile.get("kind") == "PASTURE":
                by_quadrant[quadrant]["PASTURE:" + str(tile.get("animal"))] += 1
            elif tile.get("kind") == "PLANT":
                by_quadrant[quadrant]["PLANT:" + str(tile.get("crop"))] += 1
    return {"step": int(obs["step"]), "quadrants": len(farm["unlocked_quadrants"]),
            "money": round(float(farm["money"])), "hands": len(farm.get("hands") or []),
            "se": dict(se),
            "by_quadrant": {name: dict(counts) for name, counts in by_quadrant.items()},
            "reward": float(state[seat].reward or 0)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--opponent", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--module-candidate", action="store_true")
    parser.add_argument("--steps", nargs="+", type=int,
                        default=[198, 219, 248, 254, 288, 360, 432, 600, 719])
    args = parser.parse_args()
    candidate = load(args.candidate.resolve(), args.module_candidate)
    opponent = load(args.opponent.resolve(), False)
    env, state = create_fast_episode(seed=args.seed)
    for step in sorted(set(args.steps)):
        state = run_fast_steps([candidate, opponent], env=env, state=state,
                               stop_step=step)
        print(summary(state, 0))


if __name__ == "__main__":
    main()

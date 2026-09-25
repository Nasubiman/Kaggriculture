#!/usr/bin/env python3
"""Summarize land timing and SE land use from downloaded public replays.

Download with ``kaggle competitions replay EPISODE_ID --path DIRECTORY``.
Each step's action is stored one row after the observation that produced it.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def summarize(path: Path, teams: set[str]) -> list[dict]:
    replay = json.loads(path.read_text(encoding="utf-8"))
    steps = replay["steps"]
    output = []
    for seat, team in enumerate(replay["info"]["TeamNames"]):
        if team not in teams:
            continue

        def farm(step: int) -> dict:
            obs = steps[step][seat]["observation"]
            return obs["farms"][seat]

        def quadrants(step: int) -> int:
            return len(farm(step)["unlocked_quadrants"])

        land = {}
        for step in range(1, len(steps)):
            count = quadrants(step)
            if count > quadrants(step - 1):
                # The observation at step is the result of the previous action.
                land[count] = step - 1

        def se_tiles(step: int) -> dict[str, int]:
            tiles = farm(min(step, len(steps) - 1))["tiles"]
            counts = Counter()
            for row in tiles[5:10]:
                for tile in row[5:10]:
                    if isinstance(tile, dict):
                        label = tile["kind"]
                        if label == "PLANT":
                            label += ":" + tile["crop"]
                        elif label == "PASTURE":
                            label += ":" + tile.get("animal", "UNKNOWN")
                        counts[label] += 1
            return dict(counts)

        se_step = min(432, len(steps) - 1)
        se = se_tiles(se_step)
        first_shops = steps[min(144, len(steps) - 1)][seat]["observation"]["town"]["unlocked_shops"][:2]
        fourth = land.get(4)
        fourth_cash = farm(fourth)["money"] if fourth is not None else None
        fourth_observation = (steps[fourth][seat]["observation"]
                              if fourth is not None else None)
        fourth_action = (steps[fourth + 1][seat].get("action") or {}
                         if fourth is not None and fourth + 1 < len(steps) else {})
        fourth_orders = fourth_action.get("market") or []
        output.append({
            "episode_id": replay["info"]["EpisodeId"],
            "seed": replay["info"].get("seed"),
            "team": team,
            "seat": seat,
            "opponent": replay["info"]["TeamNames"][1 - seat],
            "reward": steps[-1][seat].get("reward"),
            "first_shops": first_shops,
            "land_purchase_steps": land,
            "fourth_purchase_cash_before_market": fourth_cash,
            "fourth_purchase_shops": (fourth_observation["town"]["unlocked_shops"]
                                       if fourth_observation else None),
            "fourth_purchase_prices": (fourth_observation["market"]["prices"]
                                        if fourth_observation else None),
            "fourth_land_order_position": next(
                (index for index, order in enumerate(fourth_orders)
                 if order == ["BUY_LAND"]), None),
            "fourth_purchase_market_orders": fourth_orders,
            "hands_at_step_432": len(farm(se_step)["hands"]),
            "quadrants_at_end": quadrants(len(steps) - 1),
            "se_tiles_at_step_432": se,
            "se_tiles_by_step": {str(step): se_tiles(step)
                                 for step in (288, 360, 432, 600)},
        })
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replays", nargs="+", type=Path)
    parser.add_argument("--teams", nargs="+", default=["DSM", "DECEM", "Vadim Vasilenko"])
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    rows = [row for path in args.replays for row in summarize(path, set(args.teams))]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} player-games to {args.output}")


if __name__ == "__main__":
    main()

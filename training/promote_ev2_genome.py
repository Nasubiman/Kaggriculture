#!/usr/bin/env python3
"""Freeze an Ev2Genome into a standalone Kaggle ``main.py`` candidate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import pprint

from ev2_genome import Ev2Genome, PRODUCTS, QUADRANTS


def frozen_configuration(genome: Ev2Genome) -> dict:
    genome = genome.normalized()
    return {
        "MAX_HANDS": genome.max_hands,
        "LIQUIDATION_TURNS": genome.liquidation_turns,
        "TRAVEL_COST": genome.travel_cost,
        "CORE_HERD": genome.core_herd,
        "MID_HERD": genome.mid_herd,
        "TARGET_HERD": genome.target_herd,
        "HERD_EXPANSION_DAY": genome.herd_expansion_day,
        "HERD_FINAL_DAY": genome.herd_final_day,
        "ANIMAL_PURCHASE_LAST_DAY": genome.animal_purchase_last_day,
        "FEED_STOCK_DAYS": genome.feed_stock_days,
        "ANIMAL_SLOTS": {
            quadrant: getattr(genome, f"animal_slots_{quadrant.lower()}")
            for quadrant in QUADRANTS
        },
        "CROP_MIX": {
            "NW": {
                "MELON": genome.melon_tiles_base,
                "WHEAT": genome.wheat_nw,
                "CARROT": genome.carrot_nw,
            },
            "NE": {
                "MELON": genome.melon_ne,
                "WHEAT": genome.wheat_ne,
                "CARROT": genome.carrot_ne,
            },
            "SW": {
                "MELON": genome.melon_sw,
                "WHEAT": genome.wheat_sw,
                "CARROT": genome.carrot_sw,
            },
            "SE": {
                "MELON": genome.melon_se,
                "WHEAT": genome.wheat_se,
                "CARROT": genome.carrot_se,
            },
        },
        "MELON_TILES_MIN": genome.melon_tiles_min,
        "MELON_TILES_BASE": genome.melon_tiles_base,
        "MELON_TILES_MAX": genome.melon_tiles_max,
        "MAX_EXTRA_LAND": genome.max_extra_land,
        "LAND_OPEN_DAYS": (
            genome.first_land_day,
            genome.second_land_day,
            genome.third_land_day,
        ),
        "RESERVE_FRACTION": {
            product: getattr(genome, f"reserve_{product.lower()}")
            for product in PRODUCTS
        },
        "FERTILIZER_USE": genome.fertilizer_use,
        "FERTILIZER_MIN_GAIN": genome.fertilizer_min_gain,
        "FERTILIZER_MAX_JOBS": genome.fertilizer_max_jobs,
        "FERTILIZER_PRIORITY": genome.fertilizer_priority,
    }


FERTILIZER_MODULE_SOURCE = r'''
_EV2_BASE_AGENT = agent
_EV2_FIELD_JOBS_BASE = _field_jobs
_EV2_UNIT_ACTIONS_BASE = _unit_actions


def _profitable_fertilizer_gain(obs, tile):
    if not isinstance(tile, dict) or tile.get("kind") != "PLANT":
        return 0.0
    day = int(obs.get("day", 0) or 0)
    if day >= 27 or int(tile.get("fertilized_until_day", -1) or -1) >= day:
        return 0.0
    crop = tile.get("crop")
    planted = int(tile.get("planted_day", day) or day)
    age = day - planted
    held = int(tile.get("yield_units", 0) or 0)
    prices = ((obs.get("market", {}) or {}).get("prices", {}) or {})
    crop_price = float(prices.get(crop, 0) or 0)
    fertilizer_price = float(prices.get("FERTILIZER", 100) or 100)
    bonus_units = 0
    if crop == "MELON" and 5 <= age <= 11 and held < 6:
        active = sum(1 for future_age in (age, age + 1, age + 2)
                     if 6 <= future_age <= 12)
        bonus_units = min(max(0, 6 - held), active)
    elif crop == "STRAWBERRY" and age >= 8:
        for offset in (0, 1, 2):
            since_first = day + offset + 1 - planted - 10
            if since_first >= 0 and since_first % 2 == 0:
                production_index = since_first // 2 + 1
                if production_index <= 4:
                    bonus_units += 1
    gain = bonus_units * crop_price - fertilizer_price
    return gain if gain >= FERTILIZER_MIN_GAIN else 0.0


def _field_jobs(obs, farm, private, roles, liquidation):
    jobs = _EV2_FIELD_JOBS_BASE(obs, farm, private, roles, liquidation)
    day = int(obs.get("day", 0) or 0)
    hour = int(obs.get("hour", 0) or 0)
    stock = int((private.get("shed", {}) or {}).get("FERTILIZER", 0) or 0)
    stock += sum(int((inventory or {}).get("FERTILIZER", 0) or 0)
                 for inventory in private.get("inventories", []) or [])
    if liquidation or stock <= 0 or day >= 27 or hour > 17:
        return jobs
    urgent = {tuple(job["target"]) for job in jobs
              if int(job.get("priority", 9)) <= 1}
    candidates = []
    tiles = farm.get("tiles", []) or []
    for target, role in roles.items():
        if role[0] != "CROP" or tuple(target) in urgent:
            continue
        x, y = target
        tile = tiles[y][x]
        if (not isinstance(tile, dict)
                or int(tile.get("consecutive_unwatered", 0) or 0) >= 1):
            continue
        gain = _profitable_fertilizer_gain(obs, tile)
        if gain > 0:
            candidates.append((gain, tuple(target)))
    limit = min(stock, FERTILIZER_MAX_JOBS)
    for gain, target in sorted(candidates,
                               key=lambda pair: (-pair[0], pair[1][1], pair[1][0]))[:limit]:
        _add_job(jobs, FERTILIZER_PRIORITY, gain, target, ("FERTILIZE",),
                 need="FERTILIZER", reason="profitable_fertilizer",
                 latest_hour=17)
    return jobs


def _unit_actions(obs, config, farm, private, roles):
    result = _EV2_UNIT_ACTIONS_BASE(obs, config, farm, private, roles)
    shed_stock = int((private.get("shed", {}) or {}).get("FERTILIZER", 0) or 0)
    carried = sum(int((inventory or {}).get("FERTILIZER", 0) or 0)
                  for inventory in private.get("inventories", []) or [])
    if shed_stock <= 0 or carried > 0:
        return result
    jobs = _field_jobs(obs, farm, private, roles, False)
    if not any(job.get("reason") == "profitable_fertilizer" for job in jobs):
        return result
    positions = [farm.get("farmer", [0, 0]), *(farm.get("hands", []) or [])]
    actions = [result.get("farmer", ["PASS"]), *(result.get("hands", []) or [])]
    tiles = farm.get("tiles", []) or []
    board_size = len(tiles)
    options = []
    for index, (position, action) in enumerate(zip(positions, actions)):
        if action != ["PASS"]:
            continue
        shed = _nearest_shed(position, board_size, tiles)
        options.append((_distance(position, shed), index, shed))
    if not options:
        return result
    _, index, shed = min(options)
    position = positions[index]
    action = (["PICKUP", "FERTILIZER", 1]
              if tuple(position) == tuple(shed)
              else _bfs_first_step(tiles, position, shed))
    if index == 0:
        result["farmer"] = action
    else:
        result["hands"][index - 1] = action
    return result


def kaggle_agent(obs, config=None):
    return _EV2_BASE_AGENT(obs, config)


agent = kaggle_agent
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--genome", type=Path, required=True)
    parser.add_argument(
        "--base", type=Path, default=Path("test/0801_ev2/main.py")
    )
    parser.add_argument("--output", type=Path, default=Path("candidate_main.py"))
    args = parser.parse_args()

    values = json.loads(args.genome.read_text(encoding="utf-8"))
    fields = Ev2Genome.__dataclass_fields__
    genome = Ev2Genome(
        **{name: value for name, value in values.items() if name in fields}
    ).normalized()
    source = args.base.read_text(encoding="utf-8").rstrip()
    configuration = frozen_configuration(genome)
    lines = [
        "",
        "",
        "# Frozen by training/promote_ev2_genome.py.",
        f"_FROZEN_EV2_GENOME = {pprint.pformat(genome.to_dict(), sort_dicts=False)}",
    ]
    for name, value in configuration.items():
        lines.append(f"{name} = {pprint.pformat(value, sort_dicts=False)}")
    if genome.fertilizer_use:
        # The appendix deliberately creates a new final kaggle_agent key;
        # redefining an existing dictionary key does not change insertion order.
        lines.append(FERTILIZER_MODULE_SOURCE.strip())
    # With fertilizer disabled, no callable is defined below the engine's
    # original final agent function.
    args.output.write_text(source + "\n" + "\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {args.output} ({genome.key()})")


if __name__ == "__main__":
    main()

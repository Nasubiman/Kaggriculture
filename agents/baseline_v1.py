"""Archived history-informed Kaggriculture baseline agent.

The file is intentionally self-contained so it can be submitted directly to Kaggle.
"""

from __future__ import annotations


CROPS = {
    "WHEAT": {"seed": 10, "max_yield_day": 4, "ongoing": False},
    "CARROT": {"seed": 20, "max_yield_day": 3, "ongoing": False},
    "TOMATO": {"seed": 50, "max_yield_day": 8, "ongoing": True},
    "STRAWBERRY": {"seed": 100, "max_yield_day": 10, "ongoing": True},
    "MELON": {"seed": 80, "max_yield_day": 12, "ongoing": False},
}

SELL_FLOORS = {
    "WHEAT": 18,
    "CARROT": 20,
    "TOMATO": 30,
    "STRAWBERRY": 45,
    "MELON": 90,
    "EGG": 30,
    "MILK": 65,
    "WOOL": 80,
    "FERTILIZER": 45,
}


def _fib_hire_cost(hires_already: int) -> int:
    if hires_already <= 1:
        return 1
    previous, current = 1, 1
    for _ in range(2, hires_already + 1):
        previous, current = current, previous + current
    return current


def _move_toward(x: int, y: int, target_x: int, target_y: int) -> list[str]:
    if x < target_x:
        return ["EAST"]
    if x > target_x:
        return ["WEST"]
    if y < target_y:
        return ["SOUTH"]
    if y > target_y:
        return ["NORTH"]
    return ["PASS"]


def _crop_preferences(day: int, x: int, y: int) -> list[str]:
    if day >= 28:
        return []
    if day >= 25:
        base = ["CARROT", "WHEAT", "WHEAT", "CARROT"]
    elif day < 4:
        base = ["WHEAT", "CARROT", "WHEAT", "CARROT", "MELON"]
    elif day < 10:
        base = ["WHEAT", "MELON", "CARROT", "STRAWBERRY", "WHEAT", "TOMATO"]
    else:
        base = [
            "WHEAT",
            "MELON",
            "STRAWBERRY",
            "WHEAT",
            "MELON",
            "CARROT",
            "TOMATO",
        ]
    offset = (x * 7 + y * 11 + day) % len(base)
    return base[offset:] + base[:offset]


def _choose_crop(seed_budget: dict[str, int], day: int, x: int, y: int) -> str | None:
    for crop in _crop_preferences(day, x, y):
        if seed_budget.get(crop, 0) > 0:
            return crop
    available = [crop for crop, count in seed_budget.items() if count > 0]
    return max(available, key=lambda crop: seed_budget[crop]) if available else None


def _build_tasks(farm: dict, day: int, have_seeds: bool) -> list[tuple[int, int, int, str]]:
    tasks: list[tuple[int, int, int, str]] = []
    for y, row in enumerate(farm["tiles"]):
        for x, tile in enumerate(row):
            if tile == "LOCKED":
                continue
            if tile is None:
                if have_seeds and day < 28:
                    tasks.append((5, x, y, "PLANT"))
                continue
            if not isinstance(tile, dict):
                continue
            kind = tile.get("kind")
            if kind == "WEED":
                tasks.append((4, x, y, "DIG"))
                continue
            if kind != "PLANT":
                continue

            crop = tile.get("crop")
            crop_info = CROPS.get(crop, {})
            age = day - int(tile.get("planted_day", day))
            yield_units = int(tile.get("yield_units", 0))
            if yield_units > 0 and (
                crop_info.get("ongoing") or age >= crop_info.get("max_yield_day", 999)
            ):
                tasks.append((1, x, y, "HARVEST"))
            elif not tile.get("watered_today", False):
                priority = 0 if int(tile.get("consecutive_unwatered", 0)) >= 1 else 2
                tasks.append((priority, x, y, "WATER"))
    return tasks


def _unit_actions(obs: dict, farm: dict, private: dict) -> tuple[list[str], list[list[str]]]:
    day = int(obs.get("day", 0))
    positions = [farm["farmer"]] + list(farm.get("hands", []))
    seed_budget = dict(private.get("seeds", {}))
    tasks = _build_tasks(farm, day, sum(seed_budget.values()) > 0)
    reserved: set[tuple[int, int]] = set()
    actions: list[list[str]] = []

    for position in positions:
        x, y = position
        candidates = [
            task
            for task in tasks
            if (task[1], task[2]) not in reserved
            and (task[3] != "PLANT" or sum(seed_budget.values()) > 0)
        ]
        if not candidates:
            actions.append(["PASS"])
            continue

        priority, target_x, target_y, operation = min(
            candidates,
            key=lambda task: (
                task[0],
                abs(task[1] - x) + abs(task[2] - y),
                task[2],
                task[1],
            ),
        )
        del priority
        reserved.add((target_x, target_y))

        if (x, y) != (target_x, target_y):
            actions.append(_move_toward(x, y, target_x, target_y))
            continue
        if operation == "PLANT":
            crop = _choose_crop(seed_budget, day, x, y)
            if crop is None:
                actions.append(["PASS"])
            else:
                actions.append(["PLANT", crop])
                seed_budget[crop] -= 1
        else:
            actions.append([operation])

    return actions[0], actions[1:]


def _market_actions(obs: dict, farm: dict, private: dict) -> list[list[object]]:
    day = int(obs.get("day", 0))
    hour = int(obs.get("hour", 0))
    money = float(farm.get("money", 0))
    prices = (obs.get("market") or {}).get("prices", {})
    shed = private.get("shed", {})
    market: list[list[object]] = []

    # Realize income regularly, but wait through temporary premium-product gluts.
    for product, count in shed.items():
        if count <= 0 or product not in SELL_FLOORS:
            continue
        if day >= 27 or prices.get(product, 0) >= SELL_FLOORS[product] or count >= 60:
            market.append(["SELL", product, count])
            if len(market) == 10:
                return market

    # Expand around the timing observed among the strongest public agents.
    unlocked = len(farm.get("unlocked_quadrants", ["NW"]))
    desired_land = 1 + int(day >= 9) + int(day >= 14) + int(day >= 20)
    land_costs = [1000, 2000, 4000]
    if unlocked < desired_land and hour <= 2:
        land_cost = land_costs[unlocked - 1]
        if money >= land_cost + 750 and len(market) < 10:
            market.append(["BUY_LAND"])
            money -= land_cost

    # Hiring is unusually cheap for the first several workers and dominates top histories.
    target_hands = 8
    if money >= 2500:
        target_hands = 10
    if money >= 10000:
        target_hands = 12
    if money >= 30000:
        target_hands = 14
    hires = int(farm.get("hires_today", 0))
    while hires < target_hands and len(market) < 10:
        cost = _fib_hire_cost(hires)
        if money - cost < 400:
            break
        market.append(["HIRE"])
        money -= cost
        hires += 1

    if len(market) >= 10 or day >= 28:
        return market

    empty_tiles = sum(tile is None for row in farm["tiles"] for tile in row)
    seeds = private.get("seeds", {})
    if empty_tiles == 0 and sum(seeds.values()) >= 5:
        return market

    if day < 4:
        targets = {"WHEAT": 12, "CARROT": 10, "MELON": 3}
    elif day < 10:
        targets = {"WHEAT": 10, "CARROT": 6, "MELON": 8, "STRAWBERRY": 5, "TOMATO": 3}
    elif day < 25:
        targets = {"WHEAT": 12, "CARROT": 4, "MELON": 10, "STRAWBERRY": 8, "TOMATO": 4}
    else:
        targets = {"WHEAT": 10, "CARROT": 10}

    for crop, target in targets.items():
        missing = max(0, min(target - int(seeds.get(crop, 0)), empty_tiles + 4))
        if missing <= 0:
            continue
        affordable = max(0, int((money - 400) // CROPS[crop]["seed"]))
        quantity = min(missing, affordable)
        if quantity > 0:
            market.append(["BUY_SEED", crop, quantity])
            money -= quantity * CROPS[crop]["seed"]
        if len(market) == 10:
            break
    return market


def agent(obs: dict) -> dict:
    farms = obs.get("farms") or []
    player = int(obs.get("player", 0))
    private = obs.get("private") or {}
    if player >= len(farms):
        return {"farmer": ["PASS"], "hands": [], "market": []}

    farm = farms[player]
    farmer, hands = _unit_actions(obs, farm, private)
    market = _market_actions(obs, farm, private)
    return {"farmer": farmer, "hands": hands, "market": market}

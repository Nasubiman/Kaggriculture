"""Pulse Breaker v2: a deterministic counter-strategy for Harvest Pulse.

This single-file agent keeps Harvest Pulse's stable fixed plot plan while
selling each harvested melon batch immediately. Against an opponent that clips
melon sales to two units per turn, the early sale captures the high-price part
of the shared market and lowers the price of the opponent's later sales.
"""

CROP_RULES = {
    "WHEAT": (10, 2, 4, 24, False),
    "CARROT": (20, 2, 3, 25, False),
    "TOMATO": (50, 8, 0, 20, True),
    "STRAWBERRY": (100, 10, 0, 18, True),
    "MELON": (80, 10, 12, 16, False),
}

MIX = (
    ("MELON", 13),
    ("CARROT", 4),
    ("WHEAT", 4),
    ("TOMATO", 2),
    ("STRAWBERRY", 2),
)
SELL_ORDER = (
    "MELON",
    "STRAWBERRY",
    "TOMATO",
    "CARROT",
    "WHEAT",
    "EGG",
    "MILK",
    "WOOL",
)
TARGET_HANDS = 7
EXTRA_WHEAT = 15
LAND_DAY = 11


def _plan(board_size, expanded=False):
    half = max(1, board_size // 2)
    shed = (half - 1, half - 1)
    cells = [(x, y) for y in range(half) for x in range(half)]
    cells.sort(
        key=lambda position: (
            -(
                abs(position[0] - shed[0])
                + abs(position[1] - shed[1])
            ),
            position[1],
            position[0],
        )
    )
    crops = []
    for crop, count in MIX:
        crops.extend([crop] * count)
    plan = dict(zip(cells, crops))

    if expanded:
        shed = (half, half - 1)
        extra = [
            (x, y)
            for y in range(half)
            for x in range(half, board_size)
        ]
        extra.sort(
            key=lambda position: (
                abs(position[0] - shed[0])
                + abs(position[1] - shed[1]),
                position[1],
                position[0],
            )
        )
        plan.update(
            {position: "WHEAT" for position in extra[:EXTRA_WHEAT]}
        )
    return plan


def _task(tile, planned_crop, day, hour, seeds):
    if tile == "LOCKED":
        return None
    if tile is None:
        last_day = CROP_RULES[planned_crop][3]
        if (
            hour <= 21
            and day <= last_day
            and seeds.get(planned_crop, 0) > 0
        ):
            return 3, ["PLANT", planned_crop]
        return None
    if not isinstance(tile, dict):
        return None
    if tile.get("kind") == "WEED":
        return 2, ["DIG"]
    if tile.get("kind") != "PLANT":
        return None

    crop = tile.get("crop", planned_crop)
    _, first_day, harvest_day, _, ongoing = CROP_RULES.get(
        crop, CROP_RULES[planned_crop]
    )
    age = day - tile.get("planted_day", day)
    amount = tile.get("yield_units", 0)

    if crop == "MELON" and age >= 10 and amount >= 6:
        return 0, ["HARVEST"]
    if not ongoing:
        if age >= harvest_day and amount > 0:
            target = (
                4
                if crop == "WHEAT"
                else 3
                if crop == "CARROT"
                else 0
            )
            if (
                target
                and amount < target
                and not tile.get("watered_today", False)
            ):
                return 0, ["WATER"]
            return 0, ["HARVEST"]
        if not tile.get("watered_today", False):
            return 1, ["WATER"]
        return None
    if not tile.get("watered_today", False):
        return 1, ["WATER"]
    if age >= first_day and amount > 0:
        return 0, ["HARVEST"]
    return None


def _move(source, target):
    x, y = source
    target_x, target_y = target
    if x < target_x:
        return ["EAST"]
    if x > target_x:
        return ["WEST"]
    if y < target_y:
        return ["SOUTH"]
    if y > target_y:
        return ["NORTH"]
    return ["PASS"]


def _unit_actions(obs, farm, private, plan, core_first=False):
    day = int(obs.get("day", 0))
    hour = int(obs.get("hour", 0))
    seeds = private.get("seeds", {}) or {}
    tiles = farm["tiles"]
    positions = [farm["farmer"], *farm.get("hands", [])]
    tasks = []

    half = max(1, len(tiles) // 2)
    for position, crop in plan.items():
        x, y = position
        result = _task(tiles[y][x], crop, day, hour, seeds)
        if result is not None:
            priority, action = result
            region = int(core_first and x >= half)
            tasks.append((region, priority, position, action))

    reserved = set()
    seed_budget = dict(seeds)
    actions = []

    for position in positions:
        x, y = position
        candidates = []
        for region, priority, target, action in tasks:
            if target in reserved:
                continue
            distance = abs(x - target[0]) + abs(y - target[1])
            candidates.append(
                (
                    region * 1000 + priority * 100 + distance,
                    distance,
                    target[1],
                    target[0],
                    target,
                    action,
                )
            )
        candidates.sort()

        selected = None
        for candidate in candidates:
            distance, action = candidate[1], candidate[-1]
            if (
                distance == 0
                and action[0] == "PLANT"
                and seed_budget.get(action[1], 0) <= 0
            ):
                continue
            selected = candidate
            break

        if selected is None:
            actions.append(["PASS"])
            continue

        distance, target, action = (
            selected[1],
            selected[-2],
            selected[-1],
        )
        reserved.add(target)
        if distance:
            actions.append(_move((x, y), target))
        else:
            if action[0] == "PLANT":
                seed_budget[action[1]] = (
                    seed_budget.get(action[1], 0) - 1
                )
            actions.append(action)

    return actions


def _market_actions(obs, farm, private, plan):
    day = int(obs.get("day", 0))
    hour = int(obs.get("hour", 0))
    shed = private.get("shed", {}) or {}
    seeds = private.get("seeds", {}) or {}
    orders = []

    for item in SELL_ORDER:
        amount = int(shed.get(item, 0))
        if amount > 0 and len(orders) < 10:
            # The key counter-strategy: capture the high-price portion now and
            # depress the opponent's clipped melon stream that follows.
            orders.append(["SELL", item, amount])

    budget = float(farm.get("money", 0))
    if (
        day >= LAND_DAY
        and "NE" not in farm.get("unlocked_quadrants", [])
        and budget >= 1000
        and len(orders) < 10
    ):
        orders.append(["BUY_LAND"])
        budget -= 1000

    needs = {}
    tiles = farm["tiles"]
    for (x, y), crop in plan.items():
        if (
            tiles[y][x] is None
            and day <= CROP_RULES[crop][3]
        ):
            needs[crop] = needs.get(crop, 0) + 1

    for crop in (
        "MELON",
        "CARROT",
        "WHEAT",
        "TOMATO",
        "STRAWBERRY",
    ):
        wanted = max(
            0,
            needs.get(crop, 0) - int(seeds.get(crop, 0)),
        )
        cost = CROP_RULES[crop][0]
        amount = min(
            wanted,
            int(max(0, budget - 100) // cost),
        )
        if amount > 0 and len(orders) < 10:
            orders.append(["BUY_SEED", crop, amount])
            budget -= amount * cost

    if day < 29 and hour <= 5:
        missing = max(
            0,
            TARGET_HANDS - len(farm.get("hands", [])),
        )
        while missing and len(orders) < 10:
            orders.append(["HIRE"])
            missing -= 1

    return orders


def agent(obs):
    farms = obs.get("farms", []) or []
    player = int(obs.get("player", 0))
    if player >= len(farms):
        return {
            "farmer": ["PASS"],
            "hands": [],
            "market": [],
        }

    farm = farms[player]
    private = obs.get("private", {}) or {}
    expanded = "NE" in farm.get("unlocked_quadrants", [])
    plan = _plan(
        len(farm.get("tiles", [])) or 10,
        expanded,
    )

    if int(obs.get("day", 0)) >= 29:
        return {
            "farmer": ["PASS"],
            "hands": [
                ["PASS"] for _ in farm.get("hands", [])
            ],
            "market": _market_actions(
                obs, farm, private, plan
            ),
        }

    actions = _unit_actions(
        obs,
        farm,
        private,
        plan,
        expanded,
    )
    return {
        "farmer": actions[0] if actions else ["PASS"],
        "hands": actions[1:],
        "market": _market_actions(
            obs, farm, private, plan
        ),
    }

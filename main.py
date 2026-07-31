"""Rui Bridge v1: staged cow/sheep agent derived from rank-1 public replays."""

import json
from functools import lru_cache


_BASE_CROP_RULES = {
    "WHEAT": (10, 2, 4, 24, False),
    "CARROT": (20, 2, 3, 25, False),
    "TOMATO": (50, 8, 0, 20, True),
    "STRAWBERRY": (100, 10, 0, 18, True),
    "MELON": (80, 10, 12, 16, False),
}
_BASE_MIX = (
    ("MELON", 13),
    ("CARROT", 4),
    ("WHEAT", 4),
    ("TOMATO", 2),
    ("STRAWBERRY", 2),
)
_BASE_SELL_ORDER = (
    "MELON",
    "STRAWBERRY",
    "TOMATO",
    "CARROT",
    "WHEAT",
    "EGG",
    "MILK",
    "WOOL",
)
_BASE_ANIMAL_PRODUCTS = {
    "GOOSE": "EGG",
    "COW": "MILK",
    "SHEEP": "WOOL",
}


def _base_plan(board_size, expanded=False):
    half = max(1, board_size // 2)
    shed = (half - 1, half - 1)
    cells = [
        (x, y)
        for y in range(half)
        for x in range(half)
    ]
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
    for crop, count in _BASE_MIX:
        crops.extend([crop] * count)
    plan = dict(zip(cells, crops))
    if expanded:
        extra = [
            (x, y)
            for y in range(half)
            for x in range(half, board_size)
        ]
        extra.sort(
            key=lambda position: (
                abs(position[0] - half)
                + abs(position[1] - (half - 1)),
                position[1],
                position[0],
            )
        )
        plan.update(
            {position: "WHEAT" for position in extra[:15]}
        )
    return plan


def _base_task(tile, planned_crop, day, hour, seeds):
    if tile == "LOCKED":
        return None
    if tile is None:
        last_day = _BASE_CROP_RULES[planned_crop][3]
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
    _, first_day, harvest_day, _, ongoing = (
        _BASE_CROP_RULES.get(
            crop, _BASE_CROP_RULES[planned_crop]
        )
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


def _base_move(source, target):
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


def _base_shed_access_tiles(board_size):
    half = board_size // 2
    return [
        (half - 1, half - 1),
        (half, half - 1),
        (half - 1, half),
        (half, half),
    ]


def _base_nearest_shed_tile(position, board_size):
    return min(
        _base_shed_access_tiles(board_size),
        key=lambda target: (
            abs(position[0] - target[0])
            + abs(position[1] - target[1]),
            target[1],
            target[0],
        ),
    )


def _base_final_harvest_tasks(farm, prices):
    tasks = []
    for y, row in enumerate(farm["tiles"]):
        for x, tile in enumerate(row):
            if not isinstance(tile, dict):
                continue
            amount = int(tile.get("yield_units", 0))
            if amount <= 0:
                continue
            if tile.get("kind") == "PLANT":
                product = tile.get("crop")
            else:
                product = _BASE_ANIMAL_PRODUCTS.get(
                    tile.get("animal")
                )
            if product in _BASE_SELL_ORDER:
                value = amount * int(prices.get(product, 1))
                tasks.append(((x, y), product, value))
    return tasks


def _base_final_day_actions(obs, farm, private):
    hour = int(obs.get("hour", 0))
    board_size = len(farm["tiles"])
    prices = (
        (obs.get("market", {}) or {}).get("prices", {}) or {}
    )
    positions = [farm["farmer"], *farm.get("hands", [])]
    inventories = private.get("inventories", []) or []
    tasks = _base_final_harvest_tasks(farm, prices)
    reserved = set()
    actions = []
    shed_tiles = set(_base_shed_access_tiles(board_size))
    remaining_actions = 24 - hour

    for unit_index, position in enumerate(positions):
        inventory = (
            inventories[unit_index]
            if unit_index < len(inventories)
            else {}
        ) or {}
        carrying = any(
            int(amount) > 0 for amount in inventory.values()
        )
        current = tuple(position)
        if carrying:
            target = _base_nearest_shed_tile(
                current, board_size
            )
            actions.append(
                ["DROP"]
                if current in shed_tiles
                else _base_move(current, target)
            )
            continue

        candidates = []
        if hour <= 17:
            for target, product, value in tasks:
                if target in reserved:
                    continue
                distance = (
                    abs(current[0] - target[0])
                    + abs(current[1] - target[1])
                )
                return_target = _base_nearest_shed_tile(
                    target, board_size
                )
                return_distance = (
                    abs(target[0] - return_target[0])
                    + abs(target[1] - return_target[1])
                )
                required = distance + 1 + return_distance + 1
                if required <= remaining_actions:
                    candidates.append(
                        (
                            -value,
                            required,
                            distance,
                            target[1],
                            target[0],
                            target,
                            product,
                        )
                    )
        if not candidates:
            actions.append(["PASS"])
            continue
        selected = min(candidates)
        target = selected[-2]
        reserved.add(target)
        actions.append(
            ["HARVEST"]
            if current == target
            else _base_move(current, target)
        )
    return actions


def _base_pending_drop_items(farm, private, actions):
    board_size = len(farm["tiles"])
    shed_tiles = set(_base_shed_access_tiles(board_size))
    positions = [farm["farmer"], *farm.get("hands", [])]
    inventories = private.get("inventories", []) or []
    pending = {}
    for unit_index, action in enumerate(actions):
        if (
            not action
            or action[0] != "DROP"
            or unit_index >= len(positions)
            or tuple(positions[unit_index]) not in shed_tiles
            or unit_index >= len(inventories)
        ):
            continue
        for item, amount in (
            inventories[unit_index] or {}
        ).items():
            if item in _BASE_SELL_ORDER and int(amount) > 0:
                pending[item] = (
                    pending.get(item, 0) + int(amount)
                )
    return pending


class _EmbeddedCropAgent:
    CROP_RULES = _BASE_CROP_RULES
    TARGET_HANDS = 6
    _plan = staticmethod(_base_plan)
    _task = staticmethod(_base_task)
    _move = staticmethod(_base_move)
    _shed_access_tiles = staticmethod(_base_shed_access_tiles)
    _nearest_shed_tile = staticmethod(
        _base_nearest_shed_tile
    )
    _final_harvest_tasks = staticmethod(
        _base_final_harvest_tasks
    )
    _final_day_actions = staticmethod(
        _base_final_day_actions
    )
    _pending_drop_items = staticmethod(
        _base_pending_drop_items
    )


crop_agent = _EmbeddedCropAgent()


COW_START_DAY = 10
COW_TARGET = 8
COW_PURCHASE_BATCH = 3
COW_HANDS = 11
COW_FIRST_PURCHASE = True
WHEAT_TILES = 0
CASH_CROP = "STRAWBERRY"
CASH_CROP_TILES = 0
WHEAT_PICKUP_BATCH = 12
COW_COST = 400
SALE_PROCEEDS_FACTOR = 0.5
SHEEP_TARGET = 8
SHEEP_COST = 500
GOOSE_TARGET = 0
GOOSE_COST = 300
LAND_TARGET = 2
LAND_FIRST_DAY = 10
LAND_SECOND_DAY = 30
HAND_RAMP_DAY = 10
HAND_RAMP_TARGET = 11
HAND_FULL_DAY = 10
OPENING_ANIMAL = "COW"
OPENING_ANIMAL_TARGET = 2
OPENING_REPLANT = True
USE_LEARNED_MACRO = False
SETUP_PRIORITY = 2
CARE_PRIORITY = 3
FERTILIZER_PRIORITY = 4
ANIMAL_HARVEST_PRIORITY = 5
CASH_WATER_PRIORITY = 6
WHEAT_TASK_PRIORITY = 8

RUI_COW_TARGETS = (
    (4, 4), (4, 3), (3, 2), (4, 2),
    (5, 3), (3, 4), (5, 4), (6, 4),
)
RUI_SHEEP_TARGETS = (
    (4, 0), (5, 0), (5, 2), (6, 2),
    (2, 3), (7, 3), (1, 4), (7, 4),
)
RUI_OPENING_PLAN = {
    (1, 0): "CARROT", (2, 0): "CARROT",
    (3, 0): "MELON", (4, 0): "MELON",
    (0, 1): "CARROT", (1, 1): "CARROT",
    (2, 1): "MELON", (3, 1): "MELON", (4, 1): "MELON",
    (0, 2): "CARROT", (1, 2): "MELON", (2, 2): "MELON",
    (3, 2): "MELON", (4, 2): "MELON",
    (0, 3): "CARROT", (1, 3): "MELON", (2, 3): "MELON",
    (3, 3): "MELON",
    (0, 4): "MELON", (1, 4): "MELON", (2, 4): "MELON",
    (3, 4): "MELON",
}
COW_SELL_ORDER = (
    "MILK",
    "FERTILIZER",
    "MELON",
    "STRAWBERRY",
    "TOMATO",
    "CARROT",
    "WHEAT",
    "EGG",
    "WOOL",
)


def _distance(source, target):
    return (
        abs(source[0] - target[0])
        + abs(source[1] - target[1])
    )


@lru_cache(maxsize=None)
def _top_half_cells(board_size):
    half = board_size // 2
    return tuple(
        (x, y)
        for y in range(half)
        for x in range(board_size)
    )


@lru_cache(maxsize=None)
def _cow_targets_for(board_size, cow_target, sheep_target):
    shed_tiles = crop_agent._shed_access_tiles(board_size)
    sheep = set(_sheep_targets_for(board_size, sheep_target))
    cells = [
        position
        for position in _top_half_cells(board_size)
        if position not in sheep
    ]
    cells.sort(
        key=lambda position: (
            min(
                _distance(position, shed)
                for shed in shed_tiles
            ),
            position[1],
            position[0],
        )
    )
    return tuple(cells[:cow_target])


def _cow_targets(board_size):
    return RUI_COW_TARGETS[:COW_TARGET]


@lru_cache(maxsize=None)
def _sheep_targets_for(board_size, sheep_target):
    half = board_size // 2
    preferred = [
        (half - 1, half - 1),
        (half - 1, half - 2),
        (half - 2, 1),
        (half - 1, 0),
    ]
    return tuple(
        position
        for position in preferred
        if 0 <= position[0] < board_size
        and 0 <= position[1] < board_size
    )[:sheep_target]


def _sheep_targets(board_size):
    return RUI_SHEEP_TARGETS[:SHEEP_TARGET]


def _goose_targets(board_size):
    occupied = set(_cow_targets(board_size)) | set(_sheep_targets(board_size))
    cells = [
        position
        for position in _top_half_cells(board_size)
        if position not in occupied
    ]
    cells.sort(key=lambda position: (_distance(position, (4, 4)), position[1], position[0]))
    return tuple(cells[:GOOSE_TARGET])


def _target_hands(day):
    if day >= HAND_FULL_DAY:
        return COW_HANDS
    if day >= HAND_RAMP_DAY:
        return HAND_RAMP_TARGET
    return crop_agent.TARGET_HANDS


@lru_cache(maxsize=None)
def _wheat_targets_for(
    board_size, cow_target, sheep_target, wheat_tiles
):
    cows = set(
        _cow_targets_for(
            board_size, cow_target, sheep_target
        )
    )
    shed_tiles = crop_agent._shed_access_tiles(board_size)
    cells = [
        position
        for position in _top_half_cells(board_size)
        if position not in cows
    ]
    cells.sort(
        key=lambda position: (
            min(
                _distance(position, shed)
                for shed in shed_tiles
            ),
            position[1],
            position[0],
        )
    )
    return tuple(cells[:wheat_tiles])


def _wheat_targets(board_size):
    return _wheat_targets_for(
        board_size,
        COW_TARGET,
        SHEEP_TARGET,
        WHEAT_TILES,
    )


@lru_cache(maxsize=None)
def _cash_crop_targets_for(
    board_size,
    cow_target,
    sheep_target,
    wheat_tiles,
    cash_crop_tiles,
):
    occupied = (
        set(_cow_targets_for(board_size, cow_target, sheep_target))
        | set(_sheep_targets_for(board_size, sheep_target))
        | set(
            _wheat_targets_for(
                board_size, cow_target, sheep_target, wheat_tiles
            )
        )
    )
    shed_tiles = crop_agent._shed_access_tiles(board_size)
    cells = [
        position
        for position in _top_half_cells(board_size)
        if position not in occupied
    ]
    cells.sort(
        key=lambda position: (
            min(_distance(position, shed) for shed in shed_tiles),
            position[1],
            position[0],
        )
    )
    return tuple(cells[:cash_crop_tiles])


def _cash_crop_targets(board_size):
    return _cash_crop_targets_for(
        board_size,
        COW_TARGET,
        SHEEP_TARGET,
        WHEAT_TILES,
        CASH_CROP_TILES,
    )


def _tile(farm, position):
    return farm["tiles"][position[1]][position[0]]


def _inventory(private, unit_index):
    inventories = private.get("inventories", []) or []
    if unit_index >= len(inventories):
        return {}
    return inventories[unit_index] or {}


def _animal_state(farm, animal=None):
    animals = {}
    for y, row in enumerate(farm["tiles"]):
        for x, tile in enumerate(row):
            if (
                isinstance(tile, dict)
                and tile.get("animal")
                and (
                    animal is None
                    or tile.get("animal") == animal
                )
            ):
                animals[(x, y)] = tile
    return animals


def _cow_state(farm):
    return _animal_state(farm, "COW")


def _owned_animal(farm, private, animal):
    deployed = len(_animal_state(farm, animal))
    shed = int((private.get("shed", {}) or {}).get(animal, 0))
    carried = sum(
        int((inventory or {}).get(animal, 0))
        for inventory in (
            private.get("inventories", []) or []
        )
    )
    return deployed + shed + carried


def _owned_cows(farm, private):
    return _owned_animal(farm, private, "COW")


def _available_pastures(farm, targets):
    positions = []
    for position in targets:
        tile = _tile(farm, position)
        if (
            isinstance(tile, dict)
            and tile.get("kind") == "PASTURE"
            and not tile.get("animal")
        ):
            positions.append(position)
    return positions


def _setup_tasks(obs, farm, targets, animal="COW"):
    day = int(obs.get("day", 0))
    tasks = []
    for position in targets:
        tile = _tile(farm, position)
        if tile == "LOCKED":
            continue
        if tile is None:
            tasks.append((position, ["BUILD_PASTURE"]))
        elif (
            isinstance(tile, dict)
            and tile.get("animal") == animal
        ):
            continue
        elif (
            isinstance(tile, dict)
            and tile.get("kind") == "PASTURE"
            and not tile.get("animal")
        ):
            continue
        elif isinstance(tile, dict) and tile.get("kind") == "PLANT":
            crop = tile.get("crop")
            amount = int(tile.get("yield_units", 0))
            planted_day = int(tile.get("planted_day", day))
            if (
                crop == "MELON"
                and day - planted_day < 10
            ):
                continue
            if amount > 0:
                tasks.append((position, ["HARVEST"]))
            else:
                tasks.append((position, ["DIG"]))
        else:
            tasks.append((position, ["DIG"]))
    return tasks


def _wheat_tasks(obs, farm, private, targets):
    day = int(obs.get("day", 0))
    seeds = private.get("seeds", {}) or {}
    tasks = []
    for position in targets:
        tile = _tile(farm, position)
        if tile == "LOCKED":
            continue
        if tile is None:
            if day <= 25 and int(seeds.get("WHEAT", 0)) > 0:
                tasks.append((position, ["PLANT", "WHEAT"]))
            continue
        if not isinstance(tile, dict):
            continue
        if tile.get("kind") == "WEED":
            tasks.append((position, ["DIG"]))
            continue
        if tile.get("kind") != "PLANT":
            continue
        if tile.get("crop") != "WHEAT":
            amount = int(tile.get("yield_units", 0))
            planted_day = int(tile.get("planted_day", day))
            if (
                tile.get("crop") == "MELON"
                and day - planted_day < 10
            ):
                continue
            if amount > 0:
                tasks.append((position, ["HARVEST"]))
            continue
        age = day - int(tile.get("planted_day", day))
        amount = int(tile.get("yield_units", 0))
        if age >= 4 and amount > 0:
            if amount < 4 and not tile.get("watered_today", False):
                tasks.append((position, ["WATER"]))
            else:
                tasks.append((position, ["HARVEST"]))
        elif not tile.get("watered_today", False):
            tasks.append((position, ["WATER"]))
    return tasks


def _cash_crop_tasks(obs, farm, excluded):
    day = int(obs.get("day", 0))
    tasks = []
    for y, row in enumerate(farm["tiles"]):
        for x, tile in enumerate(row):
            position = (x, y)
            if (
                position in excluded
                or not isinstance(tile, dict)
                or tile.get("kind") != "PLANT"
            ):
                continue
            crop = tile.get("crop")
            amount = int(tile.get("yield_units", 0))
            age = day - int(tile.get("planted_day", day))
            if crop == "MELON":
                if age >= 10 and amount > 0:
                    tasks.append((0, position, ["HARVEST"]))
                elif not tile.get("watered_today", False):
                    tasks.append((CASH_WATER_PRIORITY, position, ["WATER"]))
            elif amount > 0:
                tasks.append((0, position, ["HARVEST"]))
    return tasks


def _planned_cash_crop_tasks(obs, farm, private, targets):
    day = int(obs.get("day", 0))
    seeds = private.get("seeds", {}) or {}
    tasks = []
    for position in targets:
        tile = _tile(farm, position)
        if tile == "LOCKED":
            continue
        if tile is None:
            if (
                day <= _BASE_CROP_RULES[CASH_CROP][3]
                and int(seeds.get(CASH_CROP, 0)) > 0
            ):
                tasks.append((7, position, ["PLANT", CASH_CROP]))
            continue
        if not isinstance(tile, dict):
            continue
        if tile.get("kind") == "WEED":
            tasks.append((SETUP_PRIORITY, position, ["DIG"]))
            continue
        if tile.get("kind") != "PLANT":
            tasks.append((SETUP_PRIORITY, position, ["DIG"]))
            continue
        crop = tile.get("crop")
        amount = int(tile.get("yield_units", 0))
        age = day - int(tile.get("planted_day", day))
        if crop != CASH_CROP:
            if crop == "MELON" and age < 10:
                if not tile.get("watered_today", False):
                    tasks.append((CASH_WATER_PRIORITY, position, ["WATER"]))
            elif amount > 0:
                tasks.append((0, position, ["HARVEST"]))
            else:
                tasks.append((SETUP_PRIORITY, position, ["DIG"]))
            continue
        if not tile.get("watered_today", False):
            tasks.append((CASH_WATER_PRIORITY, position, ["WATER"]))
        elif amount > 0:
            tasks.append((0, position, ["HARVEST"]))
    return tasks


def _opening_animal_count(day):
    if OPENING_ANIMAL == "SHEEP":
        return min(2, SHEEP_TARGET) if day < 6 else SHEEP_TARGET
    return min(OPENING_ANIMAL_TARGET, COW_TARGET)


def _opening_animal_targets(board_size):
    if OPENING_ANIMAL == "SHEEP":
        return _sheep_targets(board_size)
    return _cow_targets(board_size)[:OPENING_ANIMAL_TARGET]


def _opening_plan(board_size):
    plan = dict(RUI_OPENING_PLAN)
    for position in _opening_animal_targets(board_size):
        plan.pop(position, None)
    return plan


def _opening_actions(obs, farm, private):
    day = int(obs.get("day", 0))
    board_size = len(farm["tiles"])
    target_count = _opening_animal_count(day)
    animal_targets = _opening_animal_targets(board_size)[:target_count]
    plan = _opening_plan(board_size)
    positions = [farm["farmer"], *farm.get("hands", [])]
    opening_animals = _animal_state(farm, OPENING_ANIMAL)
    empty_pastures = _available_pastures(
        farm, animal_targets
    )
    setup_tasks = _setup_tasks(
        obs, farm, animal_targets, OPENING_ANIMAL
    )
    crop_tasks = []
    seeds = private.get("seeds", {}) or {}
    for position, crop in plan.items():
        tile = _tile(farm, position)
        if tile is None and day > 0 and not OPENING_REPLANT:
            continue
        result = crop_agent._task(
            tile,
            crop,
            day,
            int(obs.get("hour", 0)),
            seeds,
        )
        if result is not None:
            priority, action = result
            crop_tasks.append(
                (8 + priority, position, action)
            )

    shed = private.get("shed", {}) or {}
    wheat_shed = int(shed.get("WHEAT", 0))
    animal_shed = int(shed.get(OPENING_ANIMAL, 0))
    seed_budget = dict(seeds)
    reserved = set()
    actions = []

    for unit_index, position_value in enumerate(positions):
        position = tuple(position_value)
        inventory = _inventory(private, unit_index)
        carried_animal = int(inventory.get(OPENING_ANIMAL, 0))
        carried_wheat = int(inventory.get("WHEAT", 0))
        tasks = []

        if carried_animal > 0:
            for target in empty_pastures:
                tasks.append(
                    (
                        0,
                        target,
                        ["PLACE", OPENING_ANIMAL],
                        ("PLACE_OPENING_ANIMAL", target),
                    )
                )
        elif carried_wheat > 0:
            for target, animal in opening_animals.items():
                if not animal.get("fed_today", False):
                    tasks.append(
                        (
                            1,
                            target,
                            ["FEED"],
                            ("FEED", target),
                        )
                    )

        unfed = [
            target
            for target, animal in opening_animals.items()
            if not animal.get("fed_today", False)
            and ("FEED", target) not in reserved
        ]
        if (
            carried_wheat <= 0
            and unfed
            and wheat_shed > 0
        ):
            target = crop_agent._nearest_shed_tile(
                position, board_size
            )
            amount = min(WHEAT_PICKUP_BATCH, wheat_shed)
            tasks.append(
                (
                    2,
                    target,
                    ["PICKUP", "WHEAT", amount],
                    ("PICKUP_WHEAT", unit_index),
                )
            )

        for target, animal in opening_animals.items():
            if not animal.get("cared_today", False):
                tasks.append(
                    (
                        3,
                        target,
                        ["CARE"],
                        ("CARE", target),
                    )
                )
            if animal.get("fertilizer_available", False):
                tasks.append(
                    (
                        4,
                        target,
                        ["COLLECT_FERTILIZER"],
                        ("FERTILIZER", target),
                    )
                )
            if int(animal.get("yield_units", 0)) > 0:
                tasks.append(
                    (
                        5,
                        target,
                        ["HARVEST"],
                        ("ANIMAL_PRODUCT", target),
                    )
                )

        if (
            carried_animal <= 0
            and animal_shed > 0
            and empty_pastures
        ):
            target = crop_agent._nearest_shed_tile(
                position, board_size
            )
            tasks.append(
                (
                    6,
                    target,
                    ["PICKUP", OPENING_ANIMAL, 1],
                    ("PICKUP_OPENING_ANIMAL", unit_index),
                )
            )

        for target, action in setup_tasks:
            tasks.append(
                (
                    7,
                    target,
                    action,
                    ("FIELD", target),
                )
            )
        for priority, target, action in crop_tasks:
            if (
                action[0] != "PLANT"
                or seed_budget.get(action[1], 0) > 0
            ):
                tasks.append(
                    (
                        priority,
                        target,
                        action,
                        ("FIELD", target),
                    )
                )

        selected = _choose_task(position, tasks, reserved)
        if selected is None:
            actions.append(["PASS"])
            continue
        _, distance, _, _, target, action, reservation = selected
        reserved.add(reservation)
        if distance:
            actions.append(crop_agent._move(position, target))
            continue
        actions.append(action)
        if action[0] == "PICKUP":
            if action[1] == "WHEAT":
                wheat_shed -= int(action[2])
            elif action[1] == OPENING_ANIMAL:
                animal_shed -= 1
        elif action[0] == "PLANT":
            seed_budget[action[1]] = (
                seed_budget.get(action[1], 0) - 1
            )
    return actions


def _choose_task(position, tasks, reserved):
    # This is called for every unit on almost every hour.  Keeping only the
    # current minimum avoids allocating and then scanning a large candidate
    # list while preserving Python's exact tuple ordering semantics.
    selected = None
    source_x, source_y = position
    for priority, target, action, reservation in tasks:
        if reservation in reserved:
            continue
        candidate = (
            priority,
            abs(source_x - target[0]) + abs(source_y - target[1]),
            target[1],
            target[0],
            target,
            action,
            reservation,
        )
        if selected is None or candidate < selected:
            selected = candidate
    return selected


def _cow_actions(obs, farm, private, animals=None):
    board_size = len(farm["tiles"])
    positions = [farm["farmer"], *farm.get("hands", [])]
    cow_targets = _cow_targets(board_size)
    sheep_targets = _sheep_targets(board_size)
    goose_targets = _goose_targets(board_size)
    wheat_targets = _wheat_targets(board_size)
    cash_crop_targets = _cash_crop_targets(board_size)
    if animals is None:
        animals = _animal_state(farm)
    empty_cow_pastures = _available_pastures(
        farm, cow_targets
    )
    empty_sheep_pastures = _available_pastures(
        farm, sheep_targets
    )
    empty_goose_pastures = _available_pastures(
        farm, goose_targets
    )
    setup_tasks = _setup_tasks(
        obs, farm, cow_targets, "COW"
    )
    sheep_setup_tasks = _setup_tasks(
        obs, farm, sheep_targets, "SHEEP"
    )
    goose_setup_tasks = _setup_tasks(
        obs, farm, goose_targets, "GOOSE"
    )
    wheat_tasks = _wheat_tasks(
        obs, farm, private, wheat_targets
    )
    planned_cash_crop_tasks = _planned_cash_crop_tasks(
        obs, farm, private, cash_crop_targets
    )
    cash_crop_tasks = _cash_crop_tasks(
        obs,
        farm,
        set(cow_targets)
        | set(sheep_targets)
        | set(goose_targets)
        | set(wheat_targets)
        | set(cash_crop_targets),
    )
    shed = private.get("shed", {}) or {}
    wheat_shed = int(shed.get("WHEAT", 0))
    cow_shed = int(shed.get("COW", 0))
    sheep_shed = int(shed.get("SHEEP", 0))
    goose_shed = int(shed.get("GOOSE", 0))
    reserved = set()
    actions = []
    seeds = private.get("seeds", {}) or {}
    wheat_seed_budget = int(seeds.get("WHEAT", 0))
    cash_crop_seed_budget = int(seeds.get(CASH_CROP, 0))

    animal_service_tasks = []
    for target, animal in animals.items():
        if not animal.get("cared_today", False):
            animal_service_tasks.append(
                (CARE_PRIORITY, target, ["CARE"], ("CARE", target))
            )
        if animal.get("fertilizer_available", False):
            animal_service_tasks.append(
                (
                    FERTILIZER_PRIORITY,
                    target,
                    ["COLLECT_FERTILIZER"],
                    ("FERTILIZER", target),
                )
            )
        if int(animal.get("yield_units", 0)) > 0:
            animal_service_tasks.append(
                (
                    ANIMAL_HARVEST_PRIORITY,
                    target,
                    ["HARVEST"],
                    ("ANIMAL_PRODUCT", target),
                )
            )

    field_tasks = []
    for target, action in setup_tasks:
        field_tasks.append(
            (
                0 if action[0] == "HARVEST" else SETUP_PRIORITY,
                target,
                action,
                ("FIELD", target),
            )
        )
    for target, action in sheep_setup_tasks:
        field_tasks.append(
            (
                0 if action[0] == "HARVEST" else SETUP_PRIORITY,
                target,
                action,
                ("FIELD", target),
            )
        )
    for target, action in goose_setup_tasks:
        field_tasks.append(
            (
                0 if action[0] == "HARVEST" else SETUP_PRIORITY,
                target,
                action,
                ("FIELD", target),
            )
        )
    for priority, target, action in cash_crop_tasks:
        field_tasks.append(
            (priority, target, action, ("FIELD", target))
        )
    cash_crop_nonplant_tasks = []
    cash_crop_plant_tasks = []
    for priority, target, action in planned_cash_crop_tasks:
        task = (priority, target, action, ("FIELD", target))
        if action[0] == "PLANT":
            cash_crop_plant_tasks.append(task)
        else:
            cash_crop_nonplant_tasks.append(task)
    wheat_nonplant_tasks = []
    wheat_plant_tasks = []
    for target, action in wheat_tasks:
        task = (WHEAT_TASK_PRIORITY, target, action, ("FIELD", target))
        if action[0] == "PLANT":
            wheat_plant_tasks.append(task)
        else:
            wheat_nonplant_tasks.append(task)

    for unit_index, position_value in enumerate(positions):
        position = tuple(position_value)
        inventory = _inventory(private, unit_index)
        carried_cows = int(inventory.get("COW", 0))
        carried_sheep = int(inventory.get("SHEEP", 0))
        carried_geese = int(inventory.get("GOOSE", 0))
        carried_wheat = int(inventory.get("WHEAT", 0))
        tasks = []

        if carried_cows > 0:
            for target in empty_cow_pastures:
                tasks.append(
                    (
                        0,
                        target,
                        ["PLACE", "COW"],
                        ("PLACE_COW", target),
                    )
                )
        elif carried_sheep > 0:
            for target in empty_sheep_pastures:
                tasks.append(
                    (
                        0,
                        target,
                        ["PLACE", "SHEEP"],
                        ("PLACE_SHEEP", target),
                    )
                )
        elif carried_geese > 0:
            for target in empty_goose_pastures:
                tasks.append(
                    (
                        0,
                        target,
                        ["PLACE", "GOOSE"],
                        ("PLACE_GOOSE", target),
                    )
                )
        elif carried_wheat > 0:
            for target, animal in animals.items():
                if not animal.get("fed_today", False):
                    tasks.append(
                        (
                            1,
                            target,
                            ["FEED"],
                            ("FEED", target),
                        )
                    )

        has_unfed_animal = any(
            not animal.get("fed_today", False)
            and ("FEED", target) not in reserved
            for target, animal in animals.items()
        )
        if (
            carried_wheat <= 0
            and has_unfed_animal
            and wheat_shed > 0
        ):
            target = crop_agent._nearest_shed_tile(
                position, board_size
            )
            amount = min(WHEAT_PICKUP_BATCH, wheat_shed)
            tasks.append(
                (
                    2,
                    target,
                    ["PICKUP", "WHEAT", amount],
                    ("PICKUP_WHEAT", unit_index),
                )
            )

        tasks.extend(animal_service_tasks)

        if (
            carried_cows <= 0
            and cow_shed > 0
            and empty_cow_pastures
        ):
            target = crop_agent._nearest_shed_tile(
                position, board_size
            )
            tasks.append(
                (
                    2,
                    target,
                    ["PICKUP", "COW", 1],
                    ("PICKUP_COW", unit_index),
                )
            )
        if (
            carried_sheep <= 0
            and sheep_shed > 0
            and empty_sheep_pastures
        ):
            target = crop_agent._nearest_shed_tile(
                position, board_size
            )
            tasks.append(
                (
                    2,
                    target,
                    ["PICKUP", "SHEEP", 1],
                    ("PICKUP_SHEEP", unit_index),
                )
            )
        if (
            carried_geese <= 0
            and goose_shed > 0
            and empty_goose_pastures
        ):
            target = crop_agent._nearest_shed_tile(position, board_size)
            tasks.append(
                (
                    2,
                    target,
                    ["PICKUP", "GOOSE", 1],
                    ("PICKUP_GOOSE", unit_index),
                )
            )

        tasks.extend(field_tasks)
        tasks.extend(cash_crop_nonplant_tasks)
        tasks.extend(wheat_nonplant_tasks)
        if wheat_seed_budget > 0:
            tasks.extend(wheat_plant_tasks)
        if cash_crop_seed_budget > 0:
            tasks.extend(cash_crop_plant_tasks)

        selected = _choose_task(
            position, tasks, reserved
        )
        if selected is None:
            actions.append(["PASS"])
            continue

        _, distance, _, _, target, action, reservation = selected
        reserved.add(reservation)
        if distance:
            actions.append(
                crop_agent._move(position, target)
            )
            continue

        actions.append(action)
        if action[0] == "PICKUP":
            if action[1] == "WHEAT":
                wheat_shed -= int(action[2])
            elif action[1] == "COW":
                cow_shed -= 1
            elif action[1] == "SHEEP":
                sheep_shed -= 1
            elif action[1] == "GOOSE":
                goose_shed -= 1
        elif action[0] == "PLANT":
            if action[1] == "WHEAT":
                wheat_seed_budget -= 1
            elif action[1] == CASH_CROP:
                cash_crop_seed_budget -= 1

    return actions


def _opening_market_actions(obs, farm, private):
    day = int(obs.get("day", 0))
    hour = int(obs.get("hour", 0))
    board_size = len(farm["tiles"])
    shed = private.get("shed", {}) or {}
    seeds = private.get("seeds", {}) or {}
    prices = (
        (obs.get("market", {}) or {}).get("prices", {}) or {}
    )
    money = float(farm.get("money", 0))
    orders = []

    for item in COW_SELL_ORDER:
        amount = int(shed.get(item, 0))
        if amount > 0 and len(orders) < 10:
            orders.append(["SELL", item, amount])
            money += (
                amount
                * float(prices.get(item, 1))
                * SALE_PROCEEDS_FACTOR
            )

    target_animals = _opening_animal_count(day)
    animals_missing = max(
        0,
        target_animals
        - _owned_animal(farm, private, OPENING_ANIMAL),
    )
    animal_cost = COW_COST if OPENING_ANIMAL == "COW" else SHEEP_COST
    animals_to_buy = min(
        animals_missing,
        int(max(0, money - 100) // animal_cost),
    )
    if animals_to_buy > 0 and len(orders) < 10:
        orders.append(
            ["BUY_ANIMAL", OPENING_ANIMAL, animals_to_buy]
        )
        money -= animals_to_buy * animal_cost

    wheat_carried = sum(
        int((inventory or {}).get("WHEAT", 0))
        for inventory in (
            private.get("inventories", []) or []
        )
    )
    wheat_stock = int(shed.get("WHEAT", 0)) + wheat_carried
    wheat_target = max(10, target_animals * 4)
    wheat_missing = max(0, wheat_target - wheat_stock)
    wheat_price = int(prices.get("WHEAT", 25))
    wheat_amount = min(
        wheat_missing,
        int(max(0, money - 100) // max(1, wheat_price)),
    )
    if wheat_amount > 0 and len(orders) < 10:
        orders.append(
            ["BUY_PRODUCT", "WHEAT", wheat_amount]
        )
        money -= wheat_amount * wheat_price

    plan = _opening_plan(board_size)
    needs = {}
    for position, crop in plan.items():
        tile = _tile(farm, position)
        if (
            tile is None
            and day <= crop_agent.CROP_RULES[crop][3]
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
        cost = crop_agent.CROP_RULES[crop][0]
        amount = min(
            wanted,
            int(max(0, money - 100) // cost),
        )
        if amount > 0 and len(orders) < 10:
            orders.append(["BUY_SEED", crop, amount])
            money -= amount * cost

    if day < COW_START_DAY and hour <= 5:
        missing_hands = max(
            0,
            _target_hands(day)
            - len(farm.get("hands", [])),
        )
        while missing_hands and len(orders) < 10:
            orders.append(["HIRE"])
            missing_hands -= 1
    return orders


def _cow_market_actions(obs, farm, private, animals=None):
    day = int(obs.get("day", 0))
    hour = int(obs.get("hour", 0))
    shed = private.get("shed", {}) or {}
    orders = []
    money = float(farm.get("money", 0))
    prices = (
        (obs.get("market", {}) or {}).get("prices", {}) or {}
    )

    for item in COW_SELL_ORDER:
        amount = int(shed.get(item, 0))
        if amount > 0 and len(orders) < 10:
            orders.append(["SELL", item, amount])
            money += (
                amount
                * float(prices.get(item, 1))
                * SALE_PROCEEDS_FACTOR
            )

    if (
        day < 29
        and len(farm.get("unlocked_quadrants", [])) < LAND_TARGET
        and day >= (
            LAND_FIRST_DAY
            if len(farm.get("unlocked_quadrants", [])) < 2
            else LAND_SECOND_DAY
        )
        and len(orders) < 10
        and money >= 1000
    ):
        orders.append(["BUY_LAND"])
        money -= 1000

    if animals is None:
        cows_owned = _owned_cows(farm, private)
        sheep_owned = _owned_animal(farm, private, "SHEEP")
        geese_owned = _owned_animal(farm, private, "GOOSE")
    else:
        shed_counts = private.get("shed", {}) or {}
        inventories = private.get("inventories", []) or []
        deployed_cows = 0
        deployed_sheep = 0
        deployed_geese = 0
        for animal in animals.values():
            kind = animal.get("animal")
            if kind == "COW":
                deployed_cows += 1
            elif kind == "SHEEP":
                deployed_sheep += 1
            elif kind == "GOOSE":
                deployed_geese += 1
        cows_owned = (
            deployed_cows
            + int(shed_counts.get("COW", 0))
            + sum(
                int((inventory or {}).get("COW", 0))
                for inventory in inventories
            )
        )
        sheep_owned = (
            deployed_sheep
            + int(shed_counts.get("SHEEP", 0))
            + sum(
                int((inventory or {}).get("SHEEP", 0))
                for inventory in inventories
            )
        )
        geese_owned = (
            deployed_geese
            + int(shed_counts.get("GOOSE", 0))
            + sum(
                int((inventory or {}).get("GOOSE", 0))
                for inventory in inventories
            )
        )
    wheat_carried = sum(
        int((inventory or {}).get("WHEAT", 0))
        for inventory in (
            private.get("inventories", []) or []
        )
    )
    wheat_stock = int(shed.get("WHEAT", 0)) + wheat_carried
    animal_count = cows_owned + sheep_owned + geese_owned
    wheat_target = max(
        12,
        min(
            COW_TARGET + SHEEP_TARGET + GOOSE_TARGET,
            animal_count + 4,
        )
        * 2,
    )
    wheat_missing = max(0, wheat_target - wheat_stock)
    wheat_price = int(
        ((obs.get("market", {}) or {}).get("prices", {}) or {}).get(
            "WHEAT", 25
        )
    )
    wheat_amount = min(
        wheat_missing,
        int(max(0, money - 200) // max(1, wheat_price)),
    )
    if wheat_amount > 0 and len(orders) < 10:
        orders.append(
            ["BUY_PRODUCT", "WHEAT", wheat_amount]
        )
        money -= wheat_amount * wheat_price

    cows_missing = max(0, COW_TARGET - cows_owned)
    if COW_FIRST_PURCHASE:
        cows_to_buy = min(
            cows_missing,
            COW_PURCHASE_BATCH,
            int(max(0, money - 200) // COW_COST),
        )
        if cows_to_buy > 0 and len(orders) < 10:
            orders.append(
                ["BUY_ANIMAL", "COW", cows_to_buy]
            )
            money -= cows_to_buy * COW_COST

    sheep_missing = max(0, SHEEP_TARGET - sheep_owned)
    sheep_to_buy = min(
        sheep_missing,
        int(max(0, money - 200) // SHEEP_COST),
    )
    if sheep_to_buy > 0 and len(orders) < 10:
        orders.append(
            ["BUY_ANIMAL", "SHEEP", sheep_to_buy]
        )
        money -= sheep_to_buy * SHEEP_COST

    if not COW_FIRST_PURCHASE:
        cows_to_buy = min(
            cows_missing,
            COW_PURCHASE_BATCH,
            int(max(0, money - 200) // COW_COST),
        )
        if cows_to_buy > 0 and len(orders) < 10:
            orders.append(
                ["BUY_ANIMAL", "COW", cows_to_buy]
            )
            money -= cows_to_buy * COW_COST

    geese_missing = max(0, GOOSE_TARGET - geese_owned)
    geese_to_buy = min(
        geese_missing,
        int(max(0, money - 200) // GOOSE_COST),
    )
    if geese_to_buy > 0 and len(orders) < 10:
        orders.append(["BUY_ANIMAL", "GOOSE", geese_to_buy])
        money -= geese_to_buy * GOOSE_COST

    wheat_targets = _wheat_targets(len(farm["tiles"]))
    empty_wheat = sum(
        _tile(farm, position) is None
        for position in wheat_targets
    )
    seeds = private.get("seeds", {}) or {}
    seeds_missing = max(
        0,
        empty_wheat - int(seeds.get("WHEAT", 0)),
    )
    seed_amount = min(
        seeds_missing,
        int(max(0, money - 100) // 10),
    )
    if seed_amount > 0 and len(orders) < 10:
        orders.append(
            ["BUY_SEED", "WHEAT", seed_amount]
        )
        money -= seed_amount * 10

    cash_crop_targets = _cash_crop_targets(len(farm["tiles"]))
    planted_cash_crop = sum(
        isinstance(_tile(farm, position), dict)
        and _tile(farm, position).get("kind") == "PLANT"
        and _tile(farm, position).get("crop") == CASH_CROP
        for position in cash_crop_targets
    )
    cash_crop_missing = max(
        0,
        len(cash_crop_targets)
        - planted_cash_crop
        - int(seeds.get(CASH_CROP, 0)),
    )
    cash_crop_cost = _BASE_CROP_RULES[CASH_CROP][0]
    cash_crop_amount = min(
        cash_crop_missing,
        int(max(0, money - 100) // cash_crop_cost),
    )
    if cash_crop_amount > 0 and len(orders) < 10:
        orders.append(
            ["BUY_SEED", CASH_CROP, cash_crop_amount]
        )
        money -= cash_crop_amount * cash_crop_cost

    if day < 29 and hour <= 5:
        missing_hands = max(
            0,
            _target_hands(day) - len(farm.get("hands", [])),
        )
        while missing_hands and len(orders) < 10:
            orders.append(["HIRE"])
            missing_hands -= 1
    elif day == 29 and hour <= 3:
        final_tasks = len(
            crop_agent._final_harvest_tasks(
                farm, prices
            )
        )
        target_hands = min(
            COW_HANDS,
            max(0, final_tasks - 1),
        )
        missing_hands = max(
            0,
            target_hands - len(farm.get("hands", [])),
        )
        while missing_hands and len(orders) < 10:
            orders.append(["HIRE"])
            missing_hands -= 1
    return orders


def _apply_learned_macro_profile(obs):
    """Choose the day-8 livestock profile from public market state.

    The small decision tree was fitted on server-generated counterfactual
    matches.  Resetting on day 0 also keeps repeated local Arena games
    independent when the same imported module is reused.
    """
    global COW_TARGET, WHEAT_TILES

    if not USE_LEARNED_MACRO:
        return

    day = int(obs.get("day", 0))
    hour = int(obs.get("hour", 0))
    if day == 0 and hour == 0:
        COW_TARGET = 16
        WHEAT_TILES = 3
    if day != COW_START_DAY or hour != 0:
        return

    market = obs.get("market", {}) or {}
    inventory = market.get("inventory", {}) or {}
    prices = market.get("prices", {}) or {}
    carrot_inventory = int(inventory.get("CARROT", 10_000))
    wheat_price = int(prices.get("WHEAT", 25))

    WHEAT_TILES = 2
    COW_TARGET = (
        16
        if carrot_inventory > 9_975 and wheat_price <= 34
        else 15
    )


RUI_DAY0_SCRIPT = json.loads(r'''{"0":{"farmer":["PASS"],"hands":[],"market":[["HIRE"],["HIRE"],["HIRE"],["HIRE"],["HIRE"],["HIRE"],["BUY_SEED","MELON",16],["BUY_SEED","CARROT",6],["BUY_ANIMAL","COW",2]]},"1":{"farmer":["BUILD_PASTURE"],"hands":[["WEST"],["NORTH"],["PASS"],["NORTH"],["WEST"],["NORTH"]],"market":[["BUY_PRODUCT","WHEAT",5]]},"2":{"farmer":["PICKUP","COW",1],"hands":[["NORTH"],["WEST"],["PASS"],["BUILD_PASTURE"],["NORTH"],["WEST"]],"market":[]},"3":{"farmer":["PLACE","COW"],"hands":[["SOUTH"],["PLANT","MELON"],["PASS"],["NORTH"],["WEST"],["WEST"]],"market":[]},"4":{"farmer":["PICKUP","WHEAT",3],"hands":[["PICKUP","COW",1],["WATER"],["PASS"],["PLANT","MELON"],["PLANT","MELON"],["PLANT","MELON"]],"market":[]},"5":{"farmer":["FEED"],"hands":[["NORTH"],["EAST"],["PASS"],["WATER"],["WATER"],["WATER"]],"market":[]},"6":{"farmer":["CARE"],"hands":[["PLACE","COW"],["WEST"],["PASS"],["NORTH"],["NORTH"],["NORTH"]],"market":[["BUY_PRODUCT","WHEAT",1]]},"7":{"farmer":["NORTH"],"hands":[["CARE"],["WEST"],["PASS"],["PLANT","MELON"],["PLANT","MELON"],["PLANT","MELON"]],"market":[]},"8":{"farmer":["FEED"],"hands":[["NORTH"],["WEST"],["PASS"],["WATER"],["WATER"],["WATER"]],"market":[]},"9":{"farmer":["WEST"],"hands":[["WEST"],["PLANT","MELON"],["PASS"],["NORTH"],["NORTH"],["NORTH"]],"market":[["BUY_PRODUCT","WHEAT",1]]},"10":{"farmer":["WEST"],"hands":[["WEST"],["WATER"],["PASS"],["PLANT","MELON"],["PLANT","MELON"],["PLANT","MELON"]],"market":[]},"11":{"farmer":["WEST"],"hands":[["WATER"],["WEST"],["PASS"],["WATER"],["WATER"],["NORTH"]],"market":[]},"12":{"farmer":["PLANT","MELON"],"hands":[["WEST"],["PLANT","MELON"],["PASS"],["WEST"],["WEST"],["PLANT","MELON"]],"market":[]},"13":{"farmer":["WATER"],"hands":[["PLANT","MELON"],["WATER"],["PASS"],["PLANT","MELON"],["WATER"],["WEST"]],"market":[]},"14":{"farmer":["WEST"],"hands":[["WATER"],["NORTH"],["PASS"],["WATER"],["NORTH"],["PLANT","CARROT"]],"market":[]},"15":{"farmer":["PLANT","CARROT"],"hands":[["WEST"],["NORTH"],["PASS"],["WEST"],["PLANT","CARROT"],["WATER"]],"market":[]},"16":{"farmer":["WATER"],"hands":[["PLANT","CARROT"],["NORTH"],["PASS"],["WATER"],["WEST"],["EAST"]],"market":[]},"17":{"farmer":["EAST"],"hands":[["WATER"],["PLANT","CARROT"],["PASS"],["SOUTH"],["PLANT","CARROT"],["SOUTH"]],"market":[]},"18":{"farmer":["EAST"],"hands":[["EAST"],["WATER"],["PASS"],["SOUTH"],["WATER"],["EAST"]],"market":[]},"19":{"farmer":["EAST"],"hands":[["EAST"],["EAST"],["PASS"],["EAST"],["SOUTH"],["SOUTH"]],"market":[]},"20":{"farmer":["EAST"],"hands":[["EAST"],["EAST"],["PASS"],["SOUTH"],["EAST"],["EAST"]],"market":[]},"21":{"farmer":["SOUTH"],"hands":[["SOUTH"],["SOUTH"],["PASS"],["EAST"],["SOUTH"],["SOUTH"]],"market":[]},"22":{"farmer":["PASS"],"hands":[["EAST"],["EAST"],["PASS"],["SOUTH"],["EAST"],["PASS"]],"market":[]},"23":{"farmer":["PASS"],"hands":[["SOUTH"],["SOUTH"],["PASS"],["PASS"],["SOUTH"],["PASS"]],"market":[]}}''')


def agent(obs):
    day = int(obs.get("day", 0))
    if day == 0:
        return RUI_DAY0_SCRIPT[str(int(obs.get("hour", 0)))]
    _apply_learned_macro_profile(obs)
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

    if day < COW_START_DAY:
        actions = _opening_actions(obs, farm, private)
        return {
            "farmer": actions[0] if actions else ["PASS"],
            "hands": actions[1:],
            "market": _opening_market_actions(
                obs, farm, private
            ),
        }

    if day >= 29:
        actions = crop_agent._final_day_actions(
            obs, farm, private
        )
        pending = crop_agent._pending_drop_items(
            farm, private, actions
        )
        market = _cow_market_actions(obs, farm, private)
        for item, amount in pending.items():
            for order in market:
                if order[0] == "SELL" and order[1] == item:
                    order[2] += amount
                    break
            else:
                if len(market) < 10:
                    market.append(["SELL", item, amount])
        return {
            "farmer": actions[0] if actions else ["PASS"],
            "hands": actions[1:],
            "market": market,
        }

    animals = _animal_state(farm)
    actions = _cow_actions(obs, farm, private, animals)
    return {
        "farmer": actions[0] if actions else ["PASS"],
        "hands": actions[1:],
        "market": _cow_market_actions(
            obs, farm, private, animals
        ),
    }


# --- BEGIN FROZEN STRATEGY GENOME ---
# Generated by training/promote_strategy_genome.py from best_genome.json.
# The compiler and values are embedded; no project files are imported at runtime.
from dataclasses import asdict, dataclass, replace
from typing import Any

LAYOUT_FAMILIES = ("rui", "rank1", "compact", "rows", "checker")
CASH_LAYOUTS = ("near", "far")
OPENING_MODES = ("rui_scripted", "generic", "mixed")
OPENING_ANIMALS = ("COW", "SHEEP")
LIVESTOCK_POLICIES = ("fixed", "market")
STRATEGY_FAMILIES = (
    "legacy",
    "crop_rotation",
    "land_expansion",
    "market_livestock",
    "hybrid",
)
SERVICE_ORDERS = (
    "care_fertilizer_harvest",
    "care_harvest_fertilizer",
    "harvest_care_fertilizer",
    "fertilizer_care_harvest",
)

RUI_COW_ORDER = (
    (4, 4), (4, 3), (3, 2), (4, 2), (5, 3), (3, 4),
    (5, 4), (6, 4), (5, 2), (6, 2), (7, 3), (2, 3),
)
RUI_SHEEP_ORDER = (
    (4, 0), (5, 0), (5, 2), (6, 2),
    (2, 3), (7, 3), (1, 4), (7, 4),
)
RANK1_COW_ORDER = (
    (3, 4), (4, 4), (5, 4), (5, 3), (3, 5), (4, 5),
    (7, 3), (4, 6), (6, 0), (9, 4), (5, 0), (6, 1),
)
RANK1_SHEEP_ORDER = (
    (4, 2), (4, 3), (5, 3), (4, 6), (5, 2), (3, 5),
    (4, 5), (8, 4), (6, 0), (7, 0), (6, 3), (6, 4),
)


@dataclass(frozen=True)
class StrategyGenome:
    strategy_family: str = "legacy"
    opening_mode: str = "rui_scripted"
    opening_animal: str = "COW"
    opening_animals: int = 2
    opening_hands: int = 6
    opening_cows: int = 2
    opening_sheep: int = 2
    transition_day: int = 10
    cow_count: int = 8
    sheep_count: int = 8
    goose_count: int = 0
    wheat_tiles: int = 0
    cash_tiles: int = 0
    mature_hands: int = 11
    hand_ramp_day: int = 10
    hand_ramp_target: int = 11
    hand_full_day: int = 10
    land_target: int = 2
    land_first_day: int = 10
    land_second_day: int = 29
    livestock_policy: str = "fixed"
    adaptive_day: int = 7
    price_gap: int = 15
    cow_heavy_cows: int = 10
    cow_heavy_sheep: int = 2
    sheep_heavy_cows: int = 4
    sheep_heavy_sheep: int = 8
    adaptive_goose_count: int = 3
    purchase_batch: int = 3
    cow_first: bool = True
    replant: bool = True
    wheat_pickup_batch: int = 12
    sale_factor: float = 0.50
    layout_family: str = "rui"
    cash_layout: str = "near"
    mirror: bool = False
    service_order: str = "care_fertilizer_harvest"
    second_transition_day: int = 20
    late_cow_count: int = 8
    late_sheep_count: int = 8
    late_goose_count: int = 0
    late_wheat_tiles: int = 0
    late_cash_tiles: int = 0
    late_hands: int = 11
    late_service_order: str = "care_fertilizer_harvest"
    third_transition_day: int = 28
    end_cow_count: int = 8
    end_sheep_count: int = 8
    end_goose_count: int = 0
    end_wheat_tiles: int = 0
    end_cash_tiles: int = 0
    end_hands: int = 11
    end_service_order: str = "care_fertilizer_harvest"

    def normalized(self) -> "StrategyGenome":
        values = asdict(self)
        values["strategy_family"] = _choice(
            values["strategy_family"], STRATEGY_FAMILIES
        )
        values["opening_mode"] = _choice(values["opening_mode"], OPENING_MODES)
        values["opening_animal"] = _choice(values["opening_animal"], OPENING_ANIMALS)
        values["livestock_policy"] = _choice(
            values["livestock_policy"], LIVESTOCK_POLICIES
        )
        values["layout_family"] = _choice(values["layout_family"], LAYOUT_FAMILIES)
        values["cash_layout"] = _choice(values["cash_layout"], CASH_LAYOUTS)
        values["service_order"] = _choice(values["service_order"], SERVICE_ORDERS)
        values["late_service_order"] = _choice(
            values["late_service_order"], SERVICE_ORDERS
        )
        values["end_service_order"] = _choice(
            values["end_service_order"], SERVICE_ORDERS
        )
        values["opening_animals"] = _clip_int(values["opening_animals"], 1, 4)
        values["opening_hands"] = _clip_int(values["opening_hands"], 4, 8)
        values["opening_cows"] = _clip_int(values["opening_cows"], 1, 4)
        values["opening_sheep"] = _clip_int(values["opening_sheep"], 0, 4)
        values["transition_day"] = _clip_int(values["transition_day"], 7, 12)
        values["cow_count"] = _clip_int(values["cow_count"], 6, 16)
        values["sheep_count"] = _clip_int(values["sheep_count"], 2, 12)
        values["goose_count"] = _clip_int(values["goose_count"], 0, 6)
        values["wheat_tiles"] = _clip_int(values["wheat_tiles"], 0, 16)
        values["cash_tiles"] = _clip_int(values["cash_tiles"], 0, 40)
        values["mature_hands"] = _clip_int(values["mature_hands"], 8, 13)
        values["hand_ramp_day"] = _clip_int(values["hand_ramp_day"], 0, 12)
        values["hand_ramp_target"] = _clip_int(
            values["hand_ramp_target"], values["opening_hands"], 12
        )
        values["hand_full_day"] = _clip_int(
            values["hand_full_day"], values["hand_ramp_day"], 12
        )
        values["land_target"] = _clip_int(values["land_target"], 1, 4)
        values["land_first_day"] = _clip_int(values["land_first_day"], 6, 14)
        values["land_second_day"] = _clip_int(
            values["land_second_day"], values["land_first_day"], 29
        )
        values["adaptive_day"] = _clip_int(values["adaptive_day"], 6, 12)
        values["price_gap"] = _clip_int(values["price_gap"], 0, 40)
        values["cow_heavy_cows"] = _clip_int(values["cow_heavy_cows"], 6, 16)
        values["cow_heavy_sheep"] = _clip_int(values["cow_heavy_sheep"], 0, 6)
        values["sheep_heavy_cows"] = _clip_int(values["sheep_heavy_cows"], 2, 8)
        values["sheep_heavy_sheep"] = _clip_int(values["sheep_heavy_sheep"], 6, 12)
        values["adaptive_goose_count"] = _clip_int(
            values["adaptive_goose_count"], 0, 4
        )
        values["purchase_batch"] = _clip_int(values["purchase_batch"], 1, 6)
        values["wheat_pickup_batch"] = _clip_int(values["wheat_pickup_batch"], 4, 20)
        values["sale_factor"] = round(
            max(0.30, min(0.90, float(values["sale_factor"]))), 2
        )
        values["second_transition_day"] = _clip_int(
            values["second_transition_day"],
            values["transition_day"] + 3,
            26,
        )
        values["late_cow_count"] = _clip_int(values["late_cow_count"], 4, 16)
        values["late_sheep_count"] = _clip_int(values["late_sheep_count"], 0, 12)
        values["late_goose_count"] = _clip_int(values["late_goose_count"], 0, 6)
        values["late_wheat_tiles"] = _clip_int(values["late_wheat_tiles"], 0, 20)
        values["late_cash_tiles"] = _clip_int(values["late_cash_tiles"], 0, 40)
        values["late_hands"] = _clip_int(values["late_hands"], 6, 13)
        values["third_transition_day"] = _clip_int(
            values["third_transition_day"], values["second_transition_day"] + 2, 28
        )
        values["end_cow_count"] = _clip_int(values["end_cow_count"], 2, 16)
        values["end_sheep_count"] = _clip_int(values["end_sheep_count"], 0, 12)
        values["end_goose_count"] = _clip_int(values["end_goose_count"], 0, 6)
        values["end_wheat_tiles"] = _clip_int(values["end_wheat_tiles"], 0, 20)
        values["end_cash_tiles"] = _clip_int(values["end_cash_tiles"], 0, 30)
        values["end_hands"] = _clip_int(values["end_hands"], 6, 13)
        values["cow_first"] = bool(values["cow_first"])
        values["replant"] = bool(values["replant"])
        values["mirror"] = bool(values["mirror"])

        if values["opening_mode"] == "rui_scripted":
            values.update(
                opening_animal="COW",
                opening_animals=2,
                opening_hands=6,
                mirror=False,
            )

        if values["opening_mode"] == "mixed":
            values.update(opening_animal="COW", opening_animals=values["opening_cows"])

        capacity = max(23, values["land_target"] * 25 - 2)
        for names in (
            ("cow_count", "sheep_count", "goose_count", "wheat_tiles", "cash_tiles"),
            (
                "late_cow_count", "late_sheep_count", "late_goose_count",
                "late_wheat_tiles", "late_cash_tiles",
            ),
            (
                "end_cow_count", "end_sheep_count", "end_goose_count",
                "end_wheat_tiles", "end_cash_tiles",
            ),
        ):
            overflow = sum(values[name] for name in names) - capacity
            for name in reversed(names):
                if overflow <= 0:
                    break
                floor = 2 if name in ("sheep_count",) else 0
                removable = max(0, values[name] - floor)
                removed = min(removable, overflow)
                values[name] -= removed
                overflow -= removed
        return StrategyGenome(**values)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self.normalized())

    def key(self) -> str:
        values = self.to_dict()
        active = active_field_names(self)
        defaults = StrategyGenome().to_dict()
        for name in values:
            if name not in active:
                values[name] = defaults[name]
        return "|".join(f"{name}={values[name]}" for name in values)


def rank1_seed_genome() -> StrategyGenome:
    """A searchable anchor distilled from the current rank-1 public games."""
    return StrategyGenome(
        strategy_family="hybrid",
        opening_mode="mixed",
        opening_hands=6,
        opening_cows=2,
        opening_sheep=2,
        transition_day=7,
        cow_count=6,
        sheep_count=5,
        goose_count=0,
        wheat_tiles=9,
        cash_tiles=16,
        mature_hands=12,
        hand_ramp_day=1,
        hand_ramp_target=8,
        hand_full_day=9,
        land_target=3,
        land_first_day=7,
        land_second_day=10,
        livestock_policy="market",
        adaptive_day=7,
        price_gap=15,
        purchase_batch=2,
        layout_family="rank1",
        cash_layout="near",
        second_transition_day=20,
        late_cow_count=6,
        late_sheep_count=5,
        late_goose_count=1,
        late_wheat_tiles=10,
        late_cash_tiles=20,
        late_hands=12,
        third_transition_day=26,
        end_cow_count=6,
        end_sheep_count=5,
        end_goose_count=1,
        end_wheat_tiles=6,
        end_cash_tiles=4,
        end_hands=10,
        end_service_order="harvest_care_fertilizer",
    ).normalized()


def _choice(value: Any, choices: tuple[str, ...]) -> str:
    return str(value) if str(value) in choices else choices[0]


def _clip_int(value: Any, low: int, high: int) -> int:
    return max(low, min(high, int(value)))


def _unique(sequence: list[tuple[int, int]]) -> list[tuple[int, int]]:
    seen = set()
    result = []
    for item in sequence:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def layout_targets(
    genome: StrategyGenome, board_size: int = 10, phase: str = "middle"
) -> dict[str, tuple[tuple[int, int], ...]]:
    genome = genome.normalized()
    if phase == "opening":
        cow_count = genome.opening_cows
        sheep_count = genome.opening_sheep
        goose_count = 0
        wheat_tiles = 1
        cash_tiles = 1
    elif phase == "late":
        cow_count = genome.late_cow_count
        sheep_count = genome.late_sheep_count
        goose_count = genome.late_goose_count
        wheat_tiles = genome.late_wheat_tiles
        cash_tiles = genome.late_cash_tiles
    elif phase == "end":
        cow_count = genome.end_cow_count
        sheep_count = genome.end_sheep_count
        goose_count = genome.end_goose_count
        wheat_tiles = genome.end_wheat_tiles
        cash_tiles = genome.end_cash_tiles
    else:
        cow_count = genome.cow_count
        sheep_count = genome.sheep_count
        goose_count = genome.goose_count
        wheat_tiles = genome.wheat_tiles
        cash_tiles = genome.cash_tiles
    half = board_size // 2
    quadrants = (
        [(x, y) for y in range(half) for x in range(half)],
        [(x, y) for y in range(half) for x in range(half, board_size)],
        [(x, y) for y in range(half, board_size) for x in range(half)],
        [(x, y) for y in range(half, board_size) for x in range(half, board_size)],
    )
    cells = [
        position
        for quadrant in quadrants[: genome.land_target]
        for position in quadrant
    ]
    shed = ((half - 1, half - 1), (half, half - 1))

    def distance(position: tuple[int, int]) -> int:
        return min(
            abs(position[0] - target[0]) + abs(position[1] - target[1])
            for target in shed
        )

    compact = sorted(cells, key=lambda p: (distance(p), -p[1], p[0]))
    far = sorted(cells, key=lambda p: (-distance(p), p[1], p[0]))
    rows = sorted(cells, key=lambda p: (-p[1], abs(p[0] - half), p[0]))
    checker = sorted(
        cells,
        key=lambda p: ((p[0] + p[1]) % 2, distance(p), -p[1], p[0]),
    )

    if genome.layout_family == "rui":
        cow_order = _unique(list(RUI_COW_ORDER) + compact)
        sheep_order = _unique(list(RUI_SHEEP_ORDER) + far)
    elif genome.layout_family == "rank1":
        cow_order = _unique(list(RANK1_COW_ORDER) + compact)
        sheep_order = _unique(list(RANK1_SHEEP_ORDER) + compact)
    elif genome.layout_family == "rows":
        cow_order, sheep_order = rows, far
    elif genome.layout_family == "checker":
        cow_order, sheep_order = checker, list(reversed(checker))
    else:
        cow_order, sheep_order = compact, far

    available = set(cells)
    cow_order = [position for position in cow_order if position in available]
    sheep_order = [position for position in sheep_order if position in available]

    if genome.opening_mode == "rui_scripted":
        cow_order = _unique([(4, 4), (4, 3)] + cow_order)

    cows = cow_order[:cow_count]
    occupied = set(cows)
    sheep = [position for position in sheep_order if position not in occupied][
        :sheep_count
    ]
    occupied.update(sheep)
    goose = [position for position in compact if position not in occupied][
        :goose_count
    ]
    occupied.update(goose)
    remaining_near = [position for position in compact if position not in occupied]
    remaining_far = [position for position in far if position not in occupied]
    wheat = tuple(remaining_near[:wheat_tiles])
    occupied.update(wheat)
    crop_order = remaining_near if genome.cash_layout == "near" else remaining_far
    cash = tuple(
        position for position in crop_order if position not in occupied
    )[:cash_tiles]

    def mirrored(values: tuple[tuple[int, int], ...] | list[tuple[int, int]]):
        result = tuple(values)
        if genome.mirror:
            return tuple((board_size - 1 - x, y) for x, y in result)
        return result

    return {
        "cows": mirrored(cows),
        "sheep": mirrored(sheep),
        "geese": mirrored(goose),
        "wheat": mirrored(wheat),
        "cash": mirrored(cash),
    }


def configure_module(module: Any, genome: StrategyGenome):
    """Compile a genome into an independently loaded `main.py` module."""
    # A promoted main.py contains a standalone frozen-genome wrapper.  Search
    # must unwrap it first, otherwise the previous winner would overwrite each
    # newly evaluated genome on every agent call.
    if hasattr(module, "_agent_before_frozen_genome"):
        module.agent = module._agent_before_frozen_genome
    if hasattr(module, "_opening_plan_before_frozen_genome"):
        module._opening_plan = module._opening_plan_before_frozen_genome
    genome = genome.normalized()
    module.COW_START_DAY = genome.transition_day
    module.COW_PURCHASE_BATCH = genome.purchase_batch
    module.COW_FIRST_PURCHASE = genome.cow_first
    module.WHEAT_PICKUP_BATCH = genome.wheat_pickup_batch
    module.SALE_PROCEEDS_FACTOR = genome.sale_factor
    module.OPENING_ANIMAL = genome.opening_animal
    module.OPENING_ANIMAL_TARGET = genome.opening_animals
    module.OPENING_REPLANT = genome.replant
    module.USE_LEARNED_MACRO = False
    module.LAND_TARGET = genome.land_target
    module.LAND_FIRST_DAY = genome.land_first_day
    module.LAND_SECOND_DAY = genome.land_second_day
    module.HAND_RAMP_DAY = genome.hand_ramp_day
    module.HAND_RAMP_TARGET = genome.hand_ramp_target
    module.HAND_FULL_DAY = genome.hand_full_day
    module.crop_agent.TARGET_HANDS = genome.opening_hands

    phase_state: dict[str, Any] = {
        "name": None,
        "profile": None,
        "targets": layout_targets(genome, phase="opening"),
        "target_key": None,
    }
    module._cow_targets = lambda _size: phase_state["targets"]["cows"]
    module._sheep_targets = lambda _size: phase_state["targets"]["sheep"]
    module._goose_targets = lambda _size: phase_state["targets"]["geese"]
    module._wheat_targets = lambda _size: phase_state["targets"]["wheat"]
    module._cash_crop_targets = lambda _size: phase_state["targets"]["cash"]

    def phase_values(day: int) -> tuple[str, dict[str, Any]]:
        if day < genome.transition_day:
            return "opening", {
                "cows": genome.opening_cows,
                "sheep": genome.opening_sheep,
                "geese": 0,
                "wheat": 1,
                "cash": 1,
                "hands": genome.opening_hands,
                "order": genome.service_order,
            }
        if day >= genome.third_transition_day:
            return "end", {
                "cows": genome.end_cow_count,
                "sheep": genome.end_sheep_count,
                "geese": genome.end_goose_count,
                "wheat": genome.end_wheat_tiles,
                "cash": genome.end_cash_tiles,
                "hands": genome.end_hands,
                "order": genome.end_service_order,
            }
        if day >= genome.second_transition_day:
            return "late", {
                "cows": genome.late_cow_count,
                "sheep": genome.late_sheep_count,
                "geese": genome.late_goose_count,
                "wheat": genome.late_wheat_tiles,
                "cash": genome.late_cash_tiles,
                "hands": genome.late_hands,
                "order": genome.late_service_order,
            }
        return "middle", {
            "cows": genome.cow_count,
            "sheep": genome.sheep_count,
            "geese": genome.goose_count,
            "wheat": genome.wheat_tiles,
            "cash": genome.cash_tiles,
            "hands": genome.mature_hands,
            "order": genome.service_order,
        }

    def select_market_profile(obs: dict[str, Any]) -> str | None:
        day = int(obs.get("day", 0))
        if day == 0:
            phase_state["profile"] = None
        if genome.livestock_policy != "market" or day < genome.adaptive_day:
            return None
        if phase_state["profile"] is None:
            prices = ((obs.get("market", {}) or {}).get("prices", {}) or {})
            milk = int(prices.get("MILK", 200))
            wool = int(prices.get("WOOL", 220))
            egg = int(prices.get("EGG", 50))
            if wool - milk >= genome.price_gap:
                phase_state["profile"] = "sheep"
            elif milk <= 200 and egg >= 52:
                phase_state["profile"] = "goose"
            else:
                phase_state["profile"] = "cow"
        return str(phase_state["profile"])

    def apply_phase(obs: dict[str, Any]) -> None:
        day = int(obs.get("day", 0))
        phase, values = phase_values(day)
        profile = select_market_profile(obs)
        if profile == "cow":
            values.update(
                cows=genome.cow_heavy_cows,
                sheep=genome.cow_heavy_sheep,
                geese=0,
            )
        elif profile == "sheep":
            values.update(
                cows=genome.sheep_heavy_cows,
                sheep=genome.sheep_heavy_sheep,
                geese=0,
            )
        elif profile == "goose":
            values.update(
                cows=max(3, genome.sheep_heavy_cows),
                sheep=max(4, min(6, genome.sheep_heavy_sheep)),
                geese=genome.adaptive_goose_count,
            )

        module.COW_TARGET = values["cows"]
        module.SHEEP_TARGET = values["sheep"]
        module.GOOSE_TARGET = values["geese"]
        module.WHEAT_TILES = values["wheat"]
        module.CASH_CROP_TILES = values["cash"]
        module.COW_HANDS = values["hands"]
        order = values["order"].split("_")
        priorities = {name: index + 3 for index, name in enumerate(order)}
        module.CARE_PRIORITY = priorities["care"]
        module.FERTILIZER_PRIORITY = priorities["fertilizer"]
        module.ANIMAL_HARVEST_PRIORITY = priorities["harvest"]

        target_key = (
            phase,
            values["cows"], values["sheep"], values["geese"],
            values["wheat"], values["cash"],
        )
        if target_key != phase_state["target_key"]:
            adjusted = genome
            if phase == "opening":
                adjusted = replace(
                    adjusted,
                    opening_cows=values["cows"],
                    opening_sheep=values["sheep"],
                )
            elif phase == "middle":
                adjusted = replace(
                    adjusted,
                    cow_count=values["cows"], sheep_count=values["sheep"],
                    goose_count=values["geese"], wheat_tiles=values["wheat"],
                    cash_tiles=values["cash"],
                )
            elif phase == "late":
                adjusted = replace(
                    adjusted,
                    late_cow_count=values["cows"],
                    late_sheep_count=values["sheep"],
                    late_goose_count=values["geese"],
                    late_wheat_tiles=values["wheat"],
                    late_cash_tiles=values["cash"],
                )
            else:
                adjusted = replace(
                    adjusted,
                    end_cow_count=values["cows"],
                    end_sheep_count=values["sheep"],
                    end_goose_count=values["geese"],
                    end_wheat_tiles=values["wheat"],
                    end_cash_tiles=values["cash"],
                )
            phase_state["targets"] = layout_targets(adjusted, phase=phase)
            phase_state["target_key"] = target_key
        phase_state["name"] = phase

    original_agent = module.agent

    def generic_opening_plan(board_size: int):
        plan = module.crop_agent._plan(board_size, False)
        for position in module._opening_animal_targets(board_size):
            plan.pop(position, None)
        return plan

    if genome.opening_mode == "generic":
        module._opening_plan = generic_opening_plan

    def phased_agent(obs: dict[str, Any]):
        day = int(obs.get("day", 0))
        apply_phase(obs)
        if genome.opening_mode == "mixed" and day < genome.transition_day:
            farms = obs.get("farms", []) or []
            player = int(obs.get("player", 0))
            if player >= len(farms):
                return {"farmer": ["PASS"], "hands": [], "market": []}
            farm = farms[player]
            private = obs.get("private", {}) or {}
            actions = module._cow_actions(obs, farm, private)
            return {
                "farmer": actions[0] if actions else ["PASS"],
                "hands": actions[1:],
                "market": module._cow_market_actions(obs, farm, private),
            }
        if genome.opening_mode == "rui_scripted" or day > 0:
            return original_agent(obs)
        farms = obs.get("farms", []) or []
        player = int(obs.get("player", 0))
        if player >= len(farms):
            return {"farmer": ["PASS"], "hands": [], "market": []}
        farm = farms[player]
        private = obs.get("private", {}) or {}
        actions = module._opening_actions(obs, farm, private)
        return {
            "farmer": actions[0] if actions else ["PASS"],
            "hands": actions[1:],
            "market": module._opening_market_actions(obs, farm, private),
        }

    return phased_agent

_FROZEN_GENOME = {'strategy_family': 'crop_rotation',
 'opening_mode': 'rui_scripted',
 'opening_animal': 'COW',
 'opening_animals': 2,
 'opening_hands': 6,
 'opening_cows': 4,
 'opening_sheep': 2,
 'transition_day': 10,
 'cow_count': 8,
 'sheep_count': 8,
 'goose_count': 0,
 'wheat_tiles': 0,
 'cash_tiles': 0,
 'mature_hands': 11,
 'hand_ramp_day': 9,
 'hand_ramp_target': 6,
 'hand_full_day': 10,
 'land_target': 2,
 'land_first_day': 6,
 'land_second_day': 29,
 'livestock_policy': 'fixed',
 'adaptive_day': 10,
 'price_gap': 40,
 'cow_heavy_cows': 9,
 'cow_heavy_sheep': 6,
 'sheep_heavy_cows': 4,
 'sheep_heavy_sheep': 8,
 'adaptive_goose_count': 0,
 'purchase_batch': 6,
 'cow_first': True,
 'replant': True,
 'wheat_pickup_batch': 10,
 'sale_factor': 0.45,
 'layout_family': 'rui',
 'cash_layout': 'far',
 'mirror': False,
 'service_order': 'care_fertilizer_harvest',
 'second_transition_day': 20,
 'late_cow_count': 8,
 'late_sheep_count': 8,
 'late_goose_count': 0,
 'late_wheat_tiles': 20,
 'late_cash_tiles': 0,
 'late_hands': 9,
 'late_service_order': 'care_fertilizer_harvest',
 'third_transition_day': 28,
 'end_cow_count': 5,
 'end_sheep_count': 6,
 'end_goose_count': 0,
 'end_wheat_tiles': 0,
 'end_cash_tiles': 0,
 'end_hands': 9,
 'end_service_order': 'harvest_care_fertilizer'}
_opening_plan_before_frozen_genome = _opening_plan
_agent_before_frozen_genome = agent


class _FrozenModuleProxy:
    def __getattr__(self, name):
        return globals()[name]

    def __setattr__(self, name, value):
        globals()[name] = value


agent = configure_module(_FrozenModuleProxy(), StrategyGenome(**_FROZEN_GENOME))
# --- END FROZEN STRATEGY GENOME ---

"""Cow Crown v1: cow-centered agent derived from leaders' public replays."""


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
    TARGET_HANDS = 7
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


COW_START_DAY = 11
COW_TARGET = 20
COW_PURCHASE_BATCH = 12
COW_HANDS = 12
WHEAT_TILES = 2
WHEAT_PICKUP_BATCH = 8
COW_COST = 400
SALE_PROCEEDS_FACTOR = 0.65
SHEEP_TARGET = 2
SHEEP_COST = 500
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


def _top_half_cells(board_size):
    half = board_size // 2
    return [
        (x, y)
        for y in range(half)
        for x in range(board_size)
    ]


def _cow_targets(board_size):
    shed_tiles = crop_agent._shed_access_tiles(board_size)
    sheep = set(_sheep_targets(board_size))
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
    return cells[:COW_TARGET]


def _sheep_targets(board_size):
    half = board_size // 2
    preferred = [
        (half - 1, half - 1),
        (half - 1, half - 2),
        (half - 2, 1),
        (half - 1, 0),
    ]
    return [
        position
        for position in preferred
        if 0 <= position[0] < board_size
        and 0 <= position[1] < board_size
    ][:SHEEP_TARGET]


def _wheat_targets(board_size):
    cows = set(_cow_targets(board_size))
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
    return cells[:WHEAT_TILES]


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
                    tasks.append((6, position, ["WATER"]))
            elif amount > 0:
                tasks.append((0, position, ["HARVEST"]))
    return tasks


def _opening_sheep_count(day):
    return min(2, SHEEP_TARGET) if day < 6 else SHEEP_TARGET


def _opening_plan(board_size):
    plan = crop_agent._plan(board_size, False)
    for position in _sheep_targets(board_size):
        plan.pop(position, None)
    return plan


def _opening_actions(obs, farm, private):
    day = int(obs.get("day", 0))
    board_size = len(farm["tiles"])
    target_count = _opening_sheep_count(day)
    sheep_targets = _sheep_targets(board_size)[:target_count]
    plan = _opening_plan(board_size)
    positions = [farm["farmer"], *farm.get("hands", [])]
    sheep = _animal_state(farm, "SHEEP")
    empty_pastures = _available_pastures(
        farm, sheep_targets
    )
    setup_tasks = _setup_tasks(
        obs, farm, sheep_targets, "SHEEP"
    )
    crop_tasks = []
    seeds = private.get("seeds", {}) or {}
    for position, crop in plan.items():
        tile = _tile(farm, position)
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
    sheep_shed = int(shed.get("SHEEP", 0))
    seed_budget = dict(seeds)
    reserved = set()
    actions = []

    for unit_index, position_value in enumerate(positions):
        position = tuple(position_value)
        inventory = _inventory(private, unit_index)
        carried_sheep = int(inventory.get("SHEEP", 0))
        carried_wheat = int(inventory.get("WHEAT", 0))
        tasks = []

        if carried_sheep > 0:
            for target in empty_pastures:
                tasks.append(
                    (
                        0,
                        target,
                        ["PLACE", "SHEEP"],
                        ("PLACE_SHEEP", target),
                    )
                )
        elif carried_wheat > 0:
            for target, animal in sheep.items():
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
            for target, animal in sheep.items()
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

        for target, animal in sheep.items():
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
            carried_sheep <= 0
            and sheep_shed > 0
            and empty_pastures
        ):
            target = crop_agent._nearest_shed_tile(
                position, board_size
            )
            tasks.append(
                (
                    6,
                    target,
                    ["PICKUP", "SHEEP", 1],
                    ("PICKUP_SHEEP", unit_index),
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
            elif action[1] == "SHEEP":
                sheep_shed -= 1
        elif action[0] == "PLANT":
            seed_budget[action[1]] = (
                seed_budget.get(action[1], 0) - 1
            )
    return actions


def _choose_task(position, tasks, reserved):
    candidates = [
        (
            priority,
            _distance(position, target),
            target[1],
            target[0],
            target,
            action,
            reservation,
        )
        for priority, target, action, reservation in tasks
        if reservation not in reserved
    ]
    return min(candidates) if candidates else None


def _cow_actions(obs, farm, private):
    board_size = len(farm["tiles"])
    positions = [farm["farmer"], *farm.get("hands", [])]
    cow_targets = _cow_targets(board_size)
    sheep_targets = _sheep_targets(board_size)
    wheat_targets = _wheat_targets(board_size)
    cows = _cow_state(farm)
    animals = _animal_state(farm)
    empty_cow_pastures = _available_pastures(
        farm, cow_targets
    )
    empty_sheep_pastures = _available_pastures(
        farm, sheep_targets
    )
    setup_tasks = _setup_tasks(
        obs, farm, cow_targets, "COW"
    )
    sheep_setup_tasks = _setup_tasks(
        obs, farm, sheep_targets, "SHEEP"
    )
    wheat_tasks = _wheat_tasks(
        obs, farm, private, wheat_targets
    )
    cash_crop_tasks = _cash_crop_tasks(
        obs,
        farm,
        set(cow_targets)
        | set(sheep_targets)
        | set(wheat_targets),
    )
    shed = private.get("shed", {}) or {}
    wheat_shed = int(shed.get("WHEAT", 0))
    cow_shed = int(shed.get("COW", 0))
    sheep_shed = int(shed.get("SHEEP", 0))
    reserved = set()
    actions = []
    seed_budget = int(
        (private.get("seeds", {}) or {}).get("WHEAT", 0)
    )

    for unit_index, position_value in enumerate(positions):
        position = tuple(position_value)
        inventory = _inventory(private, unit_index)
        carried_cows = int(inventory.get("COW", 0))
        carried_sheep = int(inventory.get("SHEEP", 0))
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

        unfed_animals = [
            target
            for target, animal in animals.items()
            if not animal.get("fed_today", False)
            and ("FEED", target) not in reserved
        ]
        if (
            carried_wheat <= 0
            and unfed_animals
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

        for target, animal in animals.items():
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

        for target, action in setup_tasks:
            tasks.append(
                (
                    0 if action[0] == "HARVEST" else 2,
                    target,
                    action,
                    ("FIELD", target),
                )
            )
        for target, action in sheep_setup_tasks:
            tasks.append(
                (
                    0 if action[0] == "HARVEST" else 2,
                    target,
                    action,
                    ("FIELD", target),
                )
            )
        for priority, target, action in cash_crop_tasks:
            tasks.append(
                (
                    priority,
                    target,
                    action,
                    ("FIELD", target),
                )
            )
        for target, action in wheat_tasks:
            if (
                action[0] != "PLANT"
                or seed_budget > 0
            ):
                tasks.append(
                    (
                        8,
                        target,
                        action,
                        ("FIELD", target),
                    )
                )

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
        elif action[0] == "PLANT":
            seed_budget -= 1

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

    target_sheep = _opening_sheep_count(day)
    sheep_missing = max(
        0,
        target_sheep
        - _owned_animal(farm, private, "SHEEP"),
    )
    sheep_to_buy = min(
        sheep_missing,
        int(max(0, money - 100) // SHEEP_COST),
    )
    if sheep_to_buy > 0 and len(orders) < 10:
        orders.append(
            ["BUY_ANIMAL", "SHEEP", sheep_to_buy]
        )
        money -= sheep_to_buy * SHEEP_COST

    wheat_carried = sum(
        int((inventory or {}).get("WHEAT", 0))
        for inventory in (
            private.get("inventories", []) or []
        )
    )
    wheat_stock = int(shed.get("WHEAT", 0)) + wheat_carried
    wheat_target = max(10, target_sheep * 4)
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
            crop_agent.TARGET_HANDS
            - len(farm.get("hands", [])),
        )
        while missing_hands and len(orders) < 10:
            orders.append(["HIRE"])
            missing_hands -= 1
    return orders


def _cow_market_actions(obs, farm, private):
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
        and day >= COW_START_DAY
        and "NE" not in farm.get("unlocked_quadrants", [])
        and len(orders) < 10
        and money >= 1000
    ):
        orders.append(["BUY_LAND"])
        money -= 1000

    cows_owned = _owned_cows(farm, private)
    sheep_owned = _owned_animal(farm, private, "SHEEP")
    wheat_carried = sum(
        int((inventory or {}).get("WHEAT", 0))
        for inventory in (
            private.get("inventories", []) or []
        )
    )
    wheat_stock = int(shed.get("WHEAT", 0)) + wheat_carried
    animal_count = cows_owned + sheep_owned
    wheat_target = max(
        12,
        min(
            COW_TARGET + SHEEP_TARGET,
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

    cows_missing = max(0, COW_TARGET - cows_owned)
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

    if day < 29 and hour <= 5:
        missing_hands = max(
            0,
            COW_HANDS - len(farm.get("hands", [])),
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


def agent(obs):
    day = int(obs.get("day", 0))
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

    actions = _cow_actions(obs, farm, private)
    return {
        "farmer": actions[0] if actions else ["PASS"],
        "hands": actions[1:],
        "market": _cow_market_actions(
            obs, farm, private
        ),
    }

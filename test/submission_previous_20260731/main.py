from collections import deque

CROP_RULES = {
    "WHEAT": (10, 2, 4, 24, False),
    "CARROT": (20, 2, 3, 25, False),
    "TOMATO": (50, 8, 0, 19, True),
    "STRAWBERRY": (100, 10, 0, 16, True),
    "MELON": (80, 10, 12, 16, False),
}

COW_COST = 400
TARGET_HANDS_CORE = 8
TARGET_HANDS_EXPANDED = 11
LAND_DAY = 4
EXPANSION_DEADLINE = 16
EXPANSION_BUFFER = 650
TARGET_COWS = 10
FEED_TARGET = 42
_FERT_MODE = None
_FERT_PROBE = None
SELL_ORDER = (
    "MILK", "FERTILIZER", "MELON", "STRAWBERRY",
    "TOMATO", "CARROT", "WHEAT", "EGG", "WOOL",
)


def _cow_slots(board_size, expanded):
    h = board_size // 2
    slots = [(h - 1, h - 1), (h - 1, h - 2), (h - 2, h - 1)]
    if expanded:
        slots.extend([
            (h, h - 1),
            (h + 1, h - 1),
            (h + 2, h - 1),
            (h + 3, h - 1),
            (h + 4, h - 1),
            (h, h - 2),
            (h + 1, h - 2),
            (h + 2, h - 2),
            (h + 3, h - 2),
        ])
    return [p for p in slots if 0 <= p[0] < board_size and 0 <= p[1] < board_size][:TARGET_COWS]


def _shed_tiles(board_size, tiles):
    h = board_size // 2
    out = []
    for p in ((h - 1, h - 1), (h, h - 1), (h - 1, h), (h, h)):
        if 0 <= p[0] < board_size and 0 <= p[1] < board_size and tiles[p[1]][p[0]] != "LOCKED":
            out.append(p)
    return out


def _dist(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _nearest_shed(board_size, tiles, pos):
    cells = _shed_tiles(board_size, tiles)
    return min(cells, key=lambda p: (_dist(pos, p), p[1], p[0])) if cells else tuple(pos)


def _move(tiles, source, target):
    source = tuple(source)
    target = tuple(target)
    if source == target:
        return ["PASS"]
    n = len(tiles)
    q = deque([source])
    parent = {source: None}
    move_to = {}
    directions = ((1, 0, "EAST"), (-1, 0, "WEST"), (0, 1, "SOUTH"), (0, -1, "NORTH"))
    while q:
        cur = q.popleft()
        if cur == target:
            break
        ranked = sorted(
            directions,
            key=lambda d: abs(cur[0] + d[0] - target[0]) + abs(cur[1] + d[1] - target[1]),
        )
        for dx, dy, name in ranked:
            nxt = (cur[0] + dx, cur[1] + dy)
            if not (0 <= nxt[0] < n and 0 <= nxt[1] < n):
                continue
            if tiles[nxt[1]][nxt[0]] == "LOCKED" or nxt in parent:
                continue
            parent[nxt] = cur
            move_to[nxt] = name
            q.append(nxt)
    if target not in parent:
        return ["PASS"]
    cur = target
    while parent[cur] != source:
        cur = parent[cur]
        if cur is None:
            return ["PASS"]
    return [move_to[cur]]


def _inventories(private):
    return [dict(x or {}) for x in (private.get("inventories", []) or [])]


def _total(private, item):
    value = int((private.get("shed", {}) or {}).get(item, 0))
    for inv in private.get("inventories", []) or []:
        value += int((inv or {}).get(item, 0))
    return value


def _placed_cows(farm):
    return sum(
        1
        for row in farm.get("tiles", []) or []
        for tile in row
        if isinstance(tile, dict) and tile.get("animal") == "COW"
    )


def _count_public_animals(farm, animal):
    return sum(
        1
        for row in farm.get("tiles", []) or []
        for tile in row
        if isinstance(tile, dict) and tile.get("animal") == animal
    )


def _crop_plan(board_size, expanded, cow_slots):
    h = board_size // 2
    cells = []
    for y in range(h):
        for x in range(board_size if expanded else h):
            if (x, y) not in cow_slots:
                cells.append((x, y))
    shed = (h - 1, h - 1)
    cells.sort(key=lambda p: (_dist(p, shed), p[1], p[0]))
    n = len(cells)
    counts = {
        "WHEAT": max(8, round(n * 0.38)),
        "TOMATO": max(4, round(n * 0.28)),
        "CARROT": max(3, round(n * 0.16)),
        "MELON": max(2, round(n * 0.12)),
    }
    counts["STRAWBERRY"] = max(0, n - sum(counts.values()))
    while sum(counts.values()) > n:
        for crop in ("STRAWBERRY", "MELON", "CARROT", "TOMATO", "WHEAT"):
            floor = 0 if crop == "STRAWBERRY" else 2 if crop == "MELON" else 3 if crop == "CARROT" else 4 if crop == "TOMATO" else 8
            if counts[crop] > floor and sum(counts.values()) > n:
                counts[crop] -= 1
    crops = []
    for crop in ("WHEAT", "TOMATO", "CARROT", "MELON", "STRAWBERRY"):
        crops.extend([crop] * counts[crop])
    while len(crops) < n:
        crops.append("WHEAT")
    return dict(zip(cells, crops[:n]))


def _add(tasks, priority, pos, action, need=None):
    tasks.append({"priority": priority, "pos": tuple(pos), "action": list(action), "need": need})


def _animal_tasks(obs, farm, private, slots):
    global _FERT_MODE
    day = int(obs.get("day", 0))
    prices = ((obs.get("market", {}) or {}).get("prices", {}) or {})
    milk_price = int(prices.get("MILK", 160))
    tasks = []
    tiles = farm["tiles"]
    for pos in slots:
        x, y = pos
        tile = tiles[y][x]
        if tile == "LOCKED":
            continue
        if isinstance(tile, dict) and tile.get("animal") == "COW":
            if not tile.get("fed_today", False):
                _add(tasks, 0, pos, ["FEED"], "WHEAT")
            if tile.get("fertilizer_available", False) and (_FERT_MODE is not False or _total(private, "FERTILIZER") < 16):
                _add(tasks, 1, pos, ["COLLECT_FERTILIZER"])
            if day <= 27 and milk_price >= 24 and not tile.get("cared_today", False):
                _add(tasks, 2, pos, ["CARE"])
            held = int(tile.get("yield_units", 0))
            if held >= 3 or (day >= 27 and held > 0):
                _add(tasks, 1, pos, ["HARVEST"])
        elif tile is None:
            _add(tasks, 0, pos, ["BUILD_PASTURE"])
        elif isinstance(tile, dict) and tile.get("kind") == "WEED":
            _add(tasks, 0, pos, ["DIG"])
        elif isinstance(tile, dict) and tile.get("kind") == "PASTURE" and not tile.get("animal"):
            _add(tasks, 0, pos, ["PLACE", "COW"], "COW")
        elif isinstance(tile, dict) and tile.get("kind") == "PLANT":
            _add(tasks, 0, pos, ["DIG"])
    return tasks


def _crop_tasks(obs, farm, private, plan, cow_slots):
    day = int(obs.get("day", 0))
    hour = int(obs.get("hour", 0))
    seeds = private.get("seeds", {}) or {}
    tasks = []
    for pos, planned in plan.items():
        if pos in cow_slots:
            continue
        x, y = pos
        tile = farm["tiles"][y][x]
        if tile == "LOCKED":
            continue
        if tile is None:
            if day <= CROP_RULES[planned][3] and hour <= 19 and int(seeds.get(planned, 0)) > 0:
                _add(tasks, 8, pos, ["PLANT", planned])
            continue
        if not isinstance(tile, dict):
            continue
        if tile.get("kind") == "WEED":
            _add(tasks, 7, pos, ["DIG"])
            continue
        if tile.get("kind") != "PLANT":
            continue
        crop = tile.get("crop", planned)
        _, first, harvest_day, _, ongoing = CROP_RULES.get(crop, CROP_RULES[planned])
        age = day - int(tile.get("planted_day", day))
        held = int(tile.get("yield_units", 0))
        risk = int(tile.get("consecutive_unwatered", 0)) >= 1
        if not tile.get("watered_today", False):
            _add(tasks, 3 if risk or hour >= 17 else 5, pos, ["WATER"])
            continue
        if not ongoing:
            if age >= harvest_day and held > 0:
                _add(tasks, 4, pos, ["HARVEST"])
        elif age >= first and (held >= 3 or (day >= 27 and held > 0)):
            _add(tasks, 4, pos, ["HARVEST"])
    return tasks


def _task_cost(farm, pos, inv, shed, task):
    need = task["need"]
    target = task["pos"]
    if need is None or int(inv.get(need, 0)) > 0:
        return _dist(pos, target)
    if int(shed.get(need, 0)) <= 0:
        return 10000
    s = _nearest_shed(len(farm["tiles"]), farm["tiles"], pos)
    return _dist(pos, s) + 1 + _dist(s, target)


def _task_action(farm, pos, inv, shed, task):
    need = task["need"]
    if need is not None and int(inv.get(need, 0)) <= 0:
        if int(shed.get(need, 0)) <= 0:
            return ["PASS"]
        s = _nearest_shed(len(farm["tiles"]), farm["tiles"], pos)
        if tuple(pos) == tuple(s):
            return ["PICKUP", need, 1 if need == "COW" else 4]
        return _move(farm["tiles"], pos, s)
    if tuple(pos) == task["pos"]:
        return list(task["action"])
    return _move(farm["tiles"], pos, task["pos"])


def _unit_actions(obs, farm, private, cow_slots, crop_plan):
    day = int(obs.get("day", 0))
    hour = int(obs.get("hour", 0))
    positions = [tuple(farm.get("farmer", [0, 0]))] + [tuple(p) for p in farm.get("hands", [])]
    invs = _inventories(private)
    while len(invs) < len(positions):
        invs.append({})
    shed = dict(private.get("shed", {}) or {})
    tasks = _animal_tasks(obs, farm, private, cow_slots) + _crop_tasks(obs, farm, private, crop_plan, set(cow_slots))
    actions = [["PASS"] for _ in positions]
    free_units = set(range(len(positions)))
    free_tasks = set(range(len(tasks)))

    if day >= 29 and hour >= 14:
        for i, pos in enumerate(positions):
            carried = sum(int(v) for v in invs[i].values())
            s = _nearest_shed(len(farm["tiles"]), farm["tiles"], pos)
            if carried:
                actions[i] = ["DROP"] if pos == s else _move(farm["tiles"], pos, s)
            elif pos != s:
                actions[i] = _move(farm["tiles"], pos, s)
        return actions

    while free_units and free_tasks:
        best = None
        for i in free_units:
            for j in free_tasks:
                task = tasks[j]
                cost = _task_cost(farm, positions[i], invs[i], shed, task)
                if cost >= 10000:
                    continue
                key = (task["priority"], cost, task["pos"][1], task["pos"][0], i, j)
                if best is None or key < best[0]:
                    best = (key, i, j)
        if best is None:
            break
        _, i, j = best
        actions[i] = _task_action(farm, positions[i], invs[i], shed, tasks[j])
        free_units.remove(i)
        free_tasks.remove(j)

    remaining = dict(private.get("seeds", {}) or {})
    for i, action in enumerate(actions):
        if len(action) >= 2 and action[0] == "PLANT":
            crop = action[1]
            if int(remaining.get(crop, 0)) <= 0:
                actions[i] = ["PASS"]
            else:
                remaining[crop] -= 1
    return actions


def _fib(n):
    a, b = 1, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def _market_actions(obs, farm, private, cow_slots, crop_plan):
    global _FERT_MODE, _FERT_PROBE
    day = int(obs.get("day", 0))
    hour = int(obs.get("hour", 0))
    shed = private.get("shed", {}) or {}
    prices = ((obs.get("market", {}) or {}).get("prices", {}) or {})
    orders = []
    budget = float(farm.get("money", 0))
    step = int(obs.get("step", day * 24 + hour))
    if step == 0:
        _FERT_MODE = None
        _FERT_PROBE = None
    if _FERT_PROBE is not None and step > _FERT_PROBE[0]:
        old_step, old_qty, old_money = _FERT_PROBE
        now_qty = int(shed.get("FERTILIZER", 0))
        now_money = float(farm.get("money", 0))
        _FERT_MODE = bool(now_qty < old_qty or now_money > old_money)
        _FERT_PROBE = None

    placed = _placed_cows(farm)
    cows_owned = placed + _total(private, "COW")
    expanded = "NE" in (farm.get("unlocked_quadrants", []) or [])
    current_target = TARGET_COWS if expanded else 3
    wheat_reserve = max(8, placed * 2 + 3)

    # Liquidate shed stock first so the same turn can finance animals and land.
    for item in SELL_ORDER:
        if len(orders) >= 6:
            break
        amount = int(shed.get(item, 0))
        if item == "FERTILIZER":
            if _FERT_MODE is False:
                continue
            if _FERT_MODE is None:
                if _FERT_PROBE is not None or amount <= 0:
                    continue
                amount = 1
        if item == "WHEAT" and day < 29:
            amount = max(0, amount - wheat_reserve)
        if amount <= 0:
            continue
        cap = amount if day >= 29 else 24 if item in ("MILK", "FERTILIZER") else 28
        qty = min(amount, cap)
        orders.append(["SELL", item, qty])
        if item == "FERTILIZER" and _FERT_MODE is None:
            _FERT_PROBE = (step, int(shed.get("FERTILIZER", 0)), float(farm.get("money", 0)))
        if item != "FERTILIZER" or _FERT_MODE is True:
            budget += qty * max(1, int(prices.get(item, 1)))

    # Initial herd is the first capital allocation. Buy missing initial cows before
    # seeds and wheat so they cannot be starved out of the budget by crop orders.
    if not expanded and day <= 5 and cows_owned < 3 and len(orders) < 10:
        missing = 3 - cows_owned
        qty = min(missing, max(0, int((budget - 950) // COW_COST)))
        if qty > 0:
            orders.append(["BUY_ANIMAL", "COW", qty])
            budget -= qty * COW_COST
            cows_owned += qty

    # Expansion is atomic from an economic perspective: only unlock NE when the
    # same market queue can also buy every missing cow plus a feed/cash buffer.
    expansion_missing = max(0, TARGET_COWS - cows_owned)
    expansion_cost = 1000 + expansion_missing * COW_COST + EXPANSION_BUFFER
    will_expand = (
        not expanded
        and LAND_DAY <= day <= EXPANSION_DEADLINE
        and cows_owned >= 3
        and budget >= expansion_cost
        and len(orders) <= 8
    )
    if will_expand:
        orders.append(["BUY_LAND"])
        budget -= 1000
        if expansion_missing > 0 and len(orders) < 10:
            orders.append(["BUY_ANIMAL", "COW", expansion_missing])
            budget -= expansion_missing * COW_COST
            cows_owned += expansion_missing
        expanded = True
        current_target = TARGET_COWS

    # If the land is already open but a purchase was partially filled, cows still
    # take precedence over discretionary crop spending.
    if expanded and cows_owned < current_target and day <= 19 and len(orders) < 10:
        missing = current_target - cows_owned
        qty = min(missing, max(0, int((budget - EXPANSION_BUFFER) // COW_COST)))
        if qty > 0:
            orders.append(["BUY_ANIMAL", "COW", qty])
            budget -= qty * COW_COST
            cows_owned += qty

    # Feeding is essential, but keep purchases compact. Wheat is bought after cow
    # capital allocation so it cannot block the expansion order.
    wheat_total = _total(private, "WHEAT")
    wanted_wheat = max(0, max(FEED_TARGET, placed * 4 + 12) - wheat_total)
    if wanted_wheat > 0 and len(orders) < 10:
        price = max(1, int(prices.get("WHEAT", 25)))
        essential_floor = 120 if expanded else 250
        qty = min(wanted_wheat, max(0, int((budget - essential_floor) // price)))
        if qty > 0:
            orders.append(["BUY_PRODUCT", "WHEAT", qty])
            budget -= qty * price

    # Before expansion, preserve proceeds instead of immediately reinvesting all
    # revenue into seeds. Existing crops keep earning while the cow fund grows.
    saving_for_expansion = not expanded and LAND_DAY <= day <= EXPANSION_DEADLINE
    capital_floor = 3000 if saving_for_expansion else 250

    seeds = private.get("seeds", {}) or {}
    needs = {c: 0 for c in CROP_RULES}
    for (x, y), crop in crop_plan.items():
        tile = farm["tiles"][y][x]
        if tile is None and day <= CROP_RULES[crop][3]:
            needs[crop] += 1
    for crop in ("WHEAT", "TOMATO", "CARROT", "MELON", "STRAWBERRY"):
        if len(orders) >= 10:
            break
        wanted = max(0, needs[crop] - int(seeds.get(crop, 0)))
        if wanted <= 0:
            continue
        cost = CROP_RULES[crop][0]
        # During the saving phase allow a tiny wheat seed refill, but freeze the
        # expensive expansion of the crop portfolio.
        local_floor = 450 if crop == "WHEAT" and saving_for_expansion else capital_floor
        max_batch = 4 if saving_for_expansion else 16
        qty = min(wanted, max_batch, max(0, int((budget - local_floor) // cost)))
        if qty > 0:
            orders.append(["BUY_SEED", crop, qty])
            budget -= qty * cost

    desired_hands = TARGET_HANDS_EXPANDED if expanded else TARGET_HANDS_CORE
    if day < 29 and hour <= 5:
        missing = max(0, desired_hands - len(farm.get("hands", [])))
        hire_idx = int(farm.get("hires_today", 0))
        # Hiring remains allowed while saving because maintaining existing plants
        # and animals protects the capital already invested.
        while missing > 0 and len(orders) < 10:
            cost = _fib(hire_idx)
            if budget < cost + 80:
                break
            orders.append(["HIRE"])
            budget -= cost
            hire_idx += 1
            missing -= 1
    return orders[:10]


def agent(obs):
    farms = obs.get("farms", []) or []
    player = int(obs.get("player", 0))
    if player < 0 or player >= len(farms):
        return {"farmer": ["PASS"], "hands": [], "market": []}
    farm = farms[player]
    private = obs.get("private", {}) or {}
    board_size = len(farm.get("tiles", [])) or 10
    expanded = "NE" in (farm.get("unlocked_quadrants", []) or [])
    all_cow_slots = _cow_slots(board_size, expanded)
    cows_owned = _placed_cows(farm) + _total(private, "COW")
    active_count = min(len(all_cow_slots), max(3, cows_owned))
    cow_slots = all_cow_slots[:active_count]
    crop_plan = _crop_plan(board_size, expanded, set(all_cow_slots))
    actions = _unit_actions(obs, farm, private, cow_slots, crop_plan)
    return {
        "farmer": actions[0] if actions else ["PASS"],
        "hands": actions[1:] if len(actions) > 1 else [],
        "market": _market_actions(obs, farm, private, cow_slots, crop_plan),
    }

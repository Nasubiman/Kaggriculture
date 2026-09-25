"""FQ4: state-driven four-quadrant farm agent.

The macro plan follows the public Fourth Quadrant archetype: melon capital
in the opening, animals next to the shed, a shop-dependent strawberry block,
and wheat on every remaining tile of all four quadrants. Every unit is routed
each turn by a greedy tile-job assignment instead of a recorded action tape,
so the same code works for every seed, seat and shop draw.

All tunable numbers live in CONFIG so a search can override them.
"""

from __future__ import annotations

import math

# ---------------------------------------------------------------- game data
CROPS = {
    "WHEAT": {"seed": 10, "first": 2, "max_day": 4, "interval": 0, "max_yield": 6, "ongoing": False},
    "CARROT": {"seed": 20, "first": 2, "max_day": 3, "interval": 0, "max_yield": 4, "ongoing": False},
    "TOMATO": {"seed": 50, "first": 8, "max_day": 8, "interval": 1, "max_yield": 4, "ongoing": True},
    "STRAWBERRY": {"seed": 100, "first": 10, "max_day": 10, "interval": 2, "max_yield": 4, "ongoing": True},
    "MELON": {"seed": 80, "first": 10, "max_day": 12, "interval": 0, "max_yield": 6, "ongoing": False},
}
ANIMALS = {
    "GOOSE": {"cost": 300, "structure": "COOP", "first": 4, "interval": 1, "product": "EGG"},
    "COW": {"cost": 400, "structure": "PASTURE", "first": 8, "interval": 2, "product": "MILK"},
    "SHEEP": {"cost": 500, "structure": "PASTURE", "first": 6, "interval": 3, "product": "WOOL"},
}
MARKET = {
    "WHEAT": (25, 400, "sqrt", 0.80, "log", 0.20),
    "CARROT": (35, 450, "hinge", 1.00, "sqrt", 0.70),
    "TOMATO": (60, 200, "hinge", 0.40, "sqrt", 0.60),
    "STRAWBERRY": (120, 100, "sqrt", 0.70, "linear", 1.60),
    "MELON": (250, 300, "log", 0.20, "sq", 3.60),
    "EGG": (50, 332, "hinge", 0.40, "log", 0.20),
    "MILK": (160, 122, "sqrt", 0.60, "linear", 1.60),
    "WOOL": (200, 105, "log", 0.20, "sq", 3.20),
    "FERTILIZER": (100, 200, "linear", 0.40, "linear", 0.40),
}
I0 = 10000
SHOPS = {
    "BAKERY": ("EGG", "WHEAT"),
    "PIZZA_SHOP": ("MILK", "TOMATO", "WHEAT"),
    "BRUNCH_SPOT": ("EGG", "WHEAT", "STRAWBERRY"),
    "YARN_STORE": ("WOOL",),
    "ICE_CREAM_SHOP": ("STRAWBERRY", "MILK", "WHEAT"),
    "PET_CAFE": ("CARROT",),
    "SMOOTHIE_SHOP": ("STRAWBERRY", "MILK"),
    "FARMERS_MARKET": ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY"),
}
LAND_PRICES = (1000, 2000, 4000)
SHED_TILES = ((4, 4), (5, 4), (4, 5), (5, 5))
TURNS = 24
DAYS = 30
LAST_STEP = 718
SHED_CAP = 100
CARRY_KEEP = ("WHEAT", "FERTILIZER", "COW", "SHEEP", "GOOSE")
PREMIUM = ("MELON", "MILK", "WOOL", "STRAWBERRY", "CARROT", "EGG", "TOMATO")

CONFIG = {
    # opening (NW only)
    "open_melons": 8,
    "open_cows": 2,
    "open_sheep": 2,
    "open_hands": 4,
    # animal targets once more land is open
    "cows": 5,
    "cows_per_milk_shop": 2,
    "sheep": 5,
    "sheep_with_yarn": 8,
    "sheep_per_yarn": 2,
    "animal_last_day": 16,
    # strawberry block
    "straw_base": 12,
    "straw_per_shop": 5,
    "straw_max": 30,
    "straw_first_day": 1,
    "tomato_base": 0,
    "tomato_per_shop": 4,
    "tomato_max": 14,
    "tomato_last_day": 19,
    "geese": 0,
    "geese_per_egg_shop": 3,
    "straw_last_day": 17,
    "melon_last_day": 3,
    "wheat_last_day": 26,
    # land purchase days and cash reserve required after paying
    "land_days": (6, 8, 10),
    "land_reserve": 100,
    # labour
    "hands_min": 4,
    "hands_max": 12,
    "efficiency": 0.5,
    "dist_weight": 1.0,
    "zone_penalty": 0.0,
    "load_animal": 4.0,
    "load_straw": 1.8,
    "load_fill": 1.6,
    "load_melon": 1.2,
    "wheat_harvest_age": 4,
    # fertiliser: used on wheat only while cheap, always on strawberries
    "fert_wheat_below": 55,
    "fert_buy_below": 45,
    # selling: sell units while the unit price stays at or above base * ratio
    "sell_ratio": {"WHEAT": 0.9, "STRAWBERRY": 0.35, "MELON": 0.30, "MILK": 0.30,
                   "WOOL": 0.35, "FERTILIZER": 0.25, "CARROT": 0.5, "TOMATO": 0.5, "EGG": 0.5},
    "sell_ratio_late": 0.45,
    "hold_cap": {"WHEAT": 30, "STRAWBERRY": 10, "MELON": 8, "MILK": 10, "WOOL": 8,
                 "FERTILIZER": 20, "CARROT": 10, "TOMATO": 10, "EGG": 10},
    "fert_keep": 2,
    "wheat_feed_days": 1,
    "drop_at": 10,
    "premium_drop_at": 3,
    "carrot_ratio": 1.5,
    "feed_chunk": 4,
    "fert_chunk": 6,
    "liquidate_hour": 16,
    "cash_buffer": 40,
}


def _shape(func, x, T):
    x = max(0.0, x)
    if func == "linear":
        return x
    if func == "sq":
        return x * x
    if func == "sqrt":
        return math.sqrt(x)
    if func == "log":
        return math.log(1.0 + x)
    if func == "hinge":
        u = x / T
        return u + 8.0 * max(0.0, u - 1.0) ** 2
    return x


def price_at(item, inventory):
    base, T, bf, bt, af, at = MARKET[item]
    if inventory < I0:
        amp = bt * base / _shape(bf, T, T)
        p = base + amp * _shape(bf, I0 - inventory, T)
    else:
        amp = at * base / _shape(af, T, T)
        p = base - amp * _shape(af, inventory - I0, T)
    return max(1, int(round(p)))


def quadrant(x, y):
    return ("N" if y < 5 else "S") + ("W" if x < 5 else "E")


def dist(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def shed_dist(p):
    return min(dist(p, s) for s in SHED_TILES)


def nearest_shed(p):
    return min(SHED_TILES, key=lambda s: dist(p, s))


def fib_cost(n_already):
    a, b = 1, 1
    for _ in range(n_already):
        a, b = b, a + b
    return a


def hire_total(n):
    return sum(fib_cost(k) for k in range(n))


def g(d, k, default=None):
    if isinstance(d, dict):
        return d.get(k, default)
    return getattr(d, k, default)


def move(pos, target):
    x, y = pos
    tx, ty = target
    if x < tx:
        return ["EAST"]
    if x > tx:
        return ["WEST"]
    if y < ty:
        return ["SOUTH"]
    if y > ty:
        return ["NORTH"]
    return ["PASS"]


PRIORITY = {"PLACE": 12, "FEED": 10, "HARVEST": 9, "PLANT": 9, "WATER": 8, "BUILD_PASTURE": 8,
            "CARE": 7, "COLLECT_FERTILIZER": 7, "FERTILIZE": 7, "DIG": 4}


# ------------------------------------------------------------------ agent
class FQ4:
    def __init__(self, config=None):
        self.cfg = dict(CONFIG)
        if config:
            self.cfg.update(config)
        self.role = {}
        self.day_seen = -1
        self.plans = {}
        self._plan_item = {}
        self.prices = {}
        self.load = 0.0
        self.capacity = 1e9
        self._incoming = {"COW": 0, "SHEEP": 0, "GOOSE": 0}

    # ------------------------------------------------------------- roles
    def _count_roles(self, role):
        return sum(1 for r in self.role.values() if r == role)

    def _tomato_target(self, shops):
        demand = sum(1 for s in shops if "TOMATO" in SHOPS.get(s, ()))
        c = self.cfg
        return min(c["tomato_max"], c["tomato_base"] + c["tomato_per_shop"] * demand)

    def _straw_target(self, shops):
        demand = sum(1 for s in shops if "STRAWBERRY" in SHOPS.get(s, ()))
        c = self.cfg
        return min(c["straw_max"], c["straw_base"] + c["straw_per_shop"] * demand)

    def _animal_target(self, animal, n_quads, shops):
        c = self.cfg
        if n_quads == 1:
            return {"COW": c["open_cows"], "SHEEP": c["open_sheep"]}.get(animal, 0)
        milk_shops = sum(1 for s in shops if "MILK" in SHOPS.get(s, ()))
        if animal == "GOOSE":
            egg_shops = sum(1 for s in shops if "EGG" in SHOPS.get(s, ()))
            return c["geese"] + c["geese_per_egg_shop"] * egg_shops
        if animal == "COW":
            return c["cows"] + c["cows_per_milk_shop"] * milk_shops
        return (c["sheep_with_yarn"] + c["sheep_per_yarn"] * (shops.count("YARN_STORE") - 1)
                if "YARN_STORE" in shops else c["sheep"])

    def _assign_roles(self, farm, day, shops):
        tiles = farm["tiles"]
        unlocked = set(farm["unlocked_quadrants"])
        n_quads = len(unlocked)
        # grow animal targets as land opens (pastures next to the shed)
        for animal in ("COW", "SHEEP", "GOOSE"):
            short = self._animal_target(animal, n_quads, shops) - self._count_roles(animal)
            if short <= 0 or day > self.cfg["animal_last_day"]:
                continue
            free = [p for p, r in self.role.items()
                    if r in ("WHEAT", "MELON", "STRAWBERRY") and tiles[p[1]][p[0]] is None]
            fresh = [(x, y) for y in range(10) for x in range(10)
                     if quadrant(x, y) in unlocked and (x, y) not in self.role
                     and (tiles[y][x] is None or (isinstance(tiles[y][x], dict)
                                                  and tiles[y][x].get("kind") == ANIMALS[animal]["structure"]
                                                  and not tiles[y][x].get("animal")))]
            pool = sorted(fresh + free, key=lambda p: (shed_dist(p), p[1], p[0]))
            for p in pool[:short]:
                self.role[p] = animal
        cells = [(x, y) for y in range(10) for x in range(10)
                 if quadrant(x, y) in unlocked and (x, y) not in self.role]
        cells.sort(key=lambda p: (shed_dist(p), p[1], p[0]))
        c = self.cfg
        melons = c["open_melons"] if n_quads == 1 and day == 0 else 0
        straw_need = max(0, self._straw_target(shops) - self._count_roles("STRAWBERRY")) if n_quads > 1 else 0
        tomato_need = max(0, self._tomato_target(shops) - self._count_roles("TOMATO")) if n_quads > 1 else 0
        for p in cells:
            t = tiles[p[1]][p[0]]
            if isinstance(t, dict) and t.get("kind") in ("PASTURE", "COOP"):
                # inherited structure (e.g. after a hand-over): keep its animal
                a = t.get("animal")
                self.role[p] = a if a else ("GOOSE" if t["kind"] == "COOP" else "SHEEP")
            elif isinstance(t, dict) and t.get("kind") == "PLANT":
                self.role[p] = t["crop"] if t["crop"] in ("WHEAT", "MELON", "STRAWBERRY", "TOMATO") else "WHEAT"
            elif melons > 0:
                self.role[p] = "MELON"
                melons -= 1
            elif straw_need > 0 and day <= c["straw_last_day"]:
                self.role[p] = "STRAWBERRY"
                straw_need -= 1
            elif tomato_need > 0 and day <= c["tomato_last_day"]:
                self.role[p] = "TOMATO"
                tomato_need -= 1
            else:
                self.role[p] = "WHEAT"

    def _crop_for(self, p, day, shops, commit):
        c = self.cfg
        role = self.role.get(p)
        if role in ("COW", "SHEEP", "GOOSE") or role is None:
            return None
        if role == "MELON":
            if day <= c["melon_last_day"]:
                return "MELON"
            role = "WHEAT"
        if role == "WHEAT":
            if (c["straw_first_day"] <= day <= c["straw_last_day"]
                    and self._count_roles("STRAWBERRY") < self._straw_target(shops)):
                if commit:
                    self.role[p] = "STRAWBERRY"
                return "STRAWBERRY"
            if commit:
                self.role[p] = "WHEAT"
            return self._filler(day)
        if role == "TOMATO":
            if day <= c["tomato_last_day"]:
                return "TOMATO"
            if commit:
                self.role[p] = "WHEAT"
            return self._filler(day)
        if role == "STRAWBERRY":
            if day <= c["straw_last_day"]:
                return "STRAWBERRY"
            if commit:
                self.role[p] = "WHEAT"
            return self._filler(day)
        return None

    def _filler(self, day):
        """Quick crop for a free tile: carrot while it pays clearly more than wheat."""
        c = self.cfg
        if day > c["wheat_last_day"]:
            return None
        if self.load + self.cfg["load_fill"] > self.capacity:
            return None
        pr = self.prices or {}
        if pr.get("CARROT", 0) >= pr.get("WHEAT", 99) * c["carrot_ratio"] and day <= c["wheat_last_day"] + 1:
            return "CARROT"
        return "WHEAT"

    # ------------------------------------------------------------- tile jobs
    def _job(self, p, tile, day, inv, seeds_left, shed, shops, endgame, ctx):
        """Next action on tile p for a unit carrying inv: (action, needed_item)."""
        c = self.cfg
        role = self.role.get(p)
        if tile is None:
            if role in ("COW", "SHEEP", "GOOSE"):
                if ctx["animals_waiting"].get(role, 0) > ctx["empty_pastures"].get(role, 0):
                    return (["BUILD_COOP"] if role == "GOOSE" else ["BUILD_PASTURE"]), None
                return None, None
            if endgame:
                return None, None
            crop = self._crop_for(p, day, shops, False)
            if crop and seeds_left.get(crop, 0) > 0:
                return ["PLANT", crop], None
            return None, None
        if tile == "LOCKED":
            return None, None
        kind = tile.get("kind")
        if kind == "WEED":
            if day <= c["wheat_last_day"] and role is not None:
                return ["DIG"], None
            return None, None
        if kind == "PLANT":
            crop = tile["crop"]
            cd = CROPS[crop]
            age = day - tile["planted_day"]
            y = tile.get("yield_units", 0)
            watered = tile.get("watered_today")
            if y > 0 and age >= cd["first"]:
                if cd["ongoing"]:
                    return ["HARVEST"], None
                if (y >= cd["max_yield"] or age > cd["max_day"] or (age >= cd["max_day"] and watered)
                        or (crop == "WHEAT" and age >= c["wheat_harvest_age"] and watered) or endgame):
                    return ["HARVEST"], None
            if endgame:
                return None, None
            must_water = not watered and tile.get("consecutive_unwatered", 0) >= 1
            if tile.get("fertilized_until_day", -1) < day:
                want = (crop in ("STRAWBERRY", "TOMATO") and age >= cd["first"] - 1) or (
                    crop == "WHEAT" and age == 2 and ctx["fert_price"] <= c["fert_wheat_below"])
                if want:
                    if inv.get("FERTILIZER", 0) > 0:
                        return ["FERTILIZE"], None
                    if shed.get("FERTILIZER", 0) > 0 and not (must_water and not inv.get("_carrier")):
                        return (None, "FERTILIZER")
            if not watered and self._needs_water(tile, crop, cd, age, day):
                return ["WATER"], None
            return None, None
        if kind in ("PASTURE", "COOP"):
            animal = tile.get("animal")
            if animal is None:
                if role in ("COW", "SHEEP", "GOOSE") and kind == ANIMALS[role]["structure"]:
                    if inv.get(role, 0) > 0:
                        return ["PLACE", role, 1], None
                    if shed.get(role, 0) > 0:
                        return None, role
                return None, None
            if not tile.get("fed_today"):
                if inv.get("WHEAT", 0) > 0:
                    return ["FEED"], None
                if shed.get("WHEAT", 0) > 0:
                    return None, "WHEAT"
            if not tile.get("cared_today"):
                return ["CARE"], None
            if tile.get("yield_units", 0) > 0:
                return ["HARVEST"], None
            if tile.get("fertilizer_available"):
                return ["COLLECT_FERTILIZER"], None
            return None, None
        return None, None

    def _needs_water(self, tile, crop, cd, age, day):
        """Water only when it keeps the plant alive or adds yield tonight."""
        if tile.get("consecutive_unwatered", 0) >= 1:
            return True
        if not cd["ongoing"]:
            return (cd["max_day"] + 1) // 2 <= age <= cd["max_day"]
        since = day + 1 - tile["planted_day"] - cd["first"]
        producing = since >= 0 and since % cd["interval"] == 0 and since // cd["interval"] + 1 <= cd["max_yield"]
        return producing and tile.get("fertilized_until_day", -1) >= day

    # ------------------------------------------------------------- main
    def act(self, obs):
        c = self.cfg
        step = int(g(obs, "step", 0))
        me = int(g(obs, "player", 0))
        farm = obs["farms"][me]
        private = obs["private"]
        shed = dict(private["shed"])
        seeds = dict(private["seeds"])
        invs = private.get("inventories") or [{}]
        day, hour = step // TURNS, step % TURNS
        shops = list(g(obs["town"], "unlocked_shops", []) or [])
        tiles = farm["tiles"]
        unlocked = set(farm["unlocked_quadrants"])
        endgame = day >= DAYS - 1 and hour >= c["liquidate_hour"] - 4
        self.prices = dict(obs["market"]["prices"])
        self._update_load(farm["tiles"])
        self._assign_roles(farm, day, shops)

        units = [tuple(farm["farmer"])] + [tuple(h) for h in (farm.get("hands") or [])]
        n_units = len(units)
        unit_inv = [dict(invs[i]) if i < len(invs) else {} for i in range(n_units)]

        # context shared by job evaluation
        empty_pastures = {"COW": 0, "SHEEP": 0, "GOOSE": 0}
        animals = {"COW": 0, "SHEEP": 0, "GOOSE": 0}
        crops = 0
        for (x, y), r in self.role.items():
            t = tiles[y][x]
            if (isinstance(t, dict) and t.get("kind") in ("PASTURE", "COOP") and not t.get("animal")
                    and r in empty_pastures and t["kind"] == ANIMALS[r]["structure"]):
                empty_pastures[r] += 1
        for y in range(10):
            for x in range(10):
                t = tiles[y][x]
                if isinstance(t, dict):
                    if t.get("animal") in animals:
                        animals[t["animal"]] += 1
                    elif t.get("kind") == "PLANT":
                        crops += 1
        carried = {"COW": 0, "SHEEP": 0, "GOOSE": 0}
        for inv in unit_inv:
            for a in carried:
                carried[a] += inv.get(a, 0)
        ctx = {
            "fert_price": obs["market"]["prices"]["FERTILIZER"],
            "empty_pastures": empty_pastures,
            "animals_waiting": {a: shed.get(a, 0) + carried[a] for a in carried},
        }

        pending = {}
        for y in range(10):
            for x in range(10):
                if quadrant(x, y) not in unlocked:
                    continue
                a, need = self._job((x, y), tiles[y][x], day, {}, seeds, shed, shops, endgame, ctx)
                if a is not None or need is not None:
                    pending[(x, y)] = (a, need)

        for a, n in self._incoming.items():
            ctx["animals_waiting"][a] += n
        actions = self._route(units, unit_inv, tiles, unlocked, day, step, seeds, shed, shops,
                              endgame, ctx, pending)
        # goods dropped this turn reach the shed before the market phase
        projected = dict(shed)
        room = SHED_CAP - sum(shed.values())
        for i, a in enumerate(actions):
            if a and a[0] == "DROP" and units[i] in SHED_TILES:
                for k, v in unit_inv[i].items():
                    take = min(v, max(0, room))
                    if take > 0:
                        projected[k] = projected.get(k, 0) + take
                        room -= take
        market, incoming = self._market(obs, farm, projected, seeds, day, hour, shops, pending,
                                        n_units, animals, crops)
        self._incoming = incoming
        return {"farmer": actions[0], "hands": actions[1:], "market": market[:10]}

    # ------------------------------------------------------------- routing
    def _route(self, units, unit_inv, tiles, unlocked, day, step, seeds, shed, shops, endgame, ctx, pending):
        c = self.cfg
        n_units = len(units)
        if day != self.day_seen:
            self.day_seen = day
            self.plans = {}
        plans = self.plans
        actions = [["PASS"] for _ in range(n_units)]
        shed_left = dict(shed)
        plant_used = {}

        def job_for(i, p, inv):
            seeds_here = {k: seeds.get(k, 0) - plant_used.get(k, 0) for k in seeds}
            return self._job(p, tiles[p[1]][p[0]], day, inv, seeds_here, shed_left, shops, endgame, ctx)

        # prune finished targets from every plan
        for i in list(plans):
            if i >= n_units:
                del plans[i]
                continue
            keep = []
            for p in plans[i]:
                if p == "SHED":
                    keep.append(p)
                    continue
                a, need = job_for(i, p, unit_inv[i])
                if self._plan_item.get(i) == "WHEAT" and a is not None and a[0] not in ("FEED", "CARE"):
                    continue
                if a is not None or (need is not None and need == self._plan_item.get(i)):
                    keep.append(p)
            plans[i] = keep
        claimed = {p for i, pl in plans.items() for p in pl if p != "SHED"}
        zones = self._zones(n_units, pending, unlocked)

        for i in range(n_units):
            pos = units[i]
            inv = unit_inv[i]
            plan = plans.setdefault(i, [])
            at_shed = pos in SHED_TILES
            feeding = self._plan_item.get(i) == "WHEAT" and any(p != "SHED" for p in plan)
            # 1) act on the tile underfoot (own target or unclaimed tile)
            if quadrant(*pos) in unlocked and (pos in plan or pos not in claimed):
                a, _ = job_for(i, pos, inv)
                if feeding and a is not None and a[0] not in ("FEED", "CARE"):
                    # feed runs only feed and care; others collect later
                    a = None
                    if pos in plan:
                        plan.remove(pos)
                if a is not None:
                    if a[0] == "PLANT":
                        plant_used[a[1]] = plant_used.get(a[1], 0) + 1
                        self._crop_for(pos, day, shops, True)
                    actions[i] = a
                    claimed.add(pos)
                    continue
            cargo = sum(v for k, v in inv.items() if k not in CARRY_KEEP)
            premium = sum(v for k, v in inv.items() if k in PREMIUM)
            if premium >= c["premium_drop_at"]:
                cargo = max(cargo, c["drop_at"])
            final_drop = day >= DAYS - 1 and step >= LAST_STEP - shed_dist(pos) - 2
            # 2) shed work: drop cargo, collect supplies for a delivery plan
            if at_shed:
                if cargo > 0 and not feeding and sum(shed_left.values()) < SHED_CAP:
                    actions[i] = ["DROP"]
                    continue
                if plan and plan[0] == "SHED":
                    plan.pop(0)
                if not plan and not final_drop:
                    got = self._delivery(pos, inv, pending, claimed, shed_left)
                    if got:
                        item, n, targets = got
                        actions[i] = ["PICKUP", item, n]
                        shed_left[item] = shed_left.get(item, 0) - n
                        plans[i] = targets
                        self._plan_item[i] = item
                        claimed.update(targets)
                        continue
            if not at_shed and (cargo >= c["drop_at"] or final_drop or (endgame and cargo > 0)):
                actions[i] = move(pos, nearest_shed(pos))
                continue
            if final_drop:
                continue
            # 3) follow the plan
            targets = [p for p in plan if p != "SHED"]
            if plan and plan[0] == "SHED":
                actions[i] = move(pos, nearest_shed(pos))
                continue
            if targets:
                nxt = min(targets, key=lambda p: dist(pos, p))
                actions[i] = move(pos, nxt)
                continue
            # 4) pick a new job
            best, best_score, best_need = None, None, None
            for p, (a, need) in pending.items():
                if p in claimed:
                    continue
                if need is not None and inv.get(need, 0) > 0:
                    need = None
                    a = ["_"]
                if need is not None:
                    if shed_left.get(need, 0) <= 0:
                        continue
                    d = shed_dist(pos) + shed_dist(p) + 1
                else:
                    d = dist(pos, p)
                if a is not None and a[0] == "PLANT" and seeds.get(a[1], 0) - plant_used.get(a[1], 0) <= 0:
                    continue
                pri = PRIORITY.get(a[0], 7) if a is not None else 8
                pri += self._urgency(tiles[p[1]][p[0]], day, step)
                score = pri - d * c["dist_weight"]
                if zones and zones[i] is not None and quadrant(*p) != zones[i]:
                    score -= c["zone_penalty"]
                if best_score is None or score > best_score:
                    best, best_score, best_need = p, score, need
            if best is None:
                if not at_shed and cargo > 0:
                    actions[i] = move(pos, nearest_shed(pos))
                continue
            if best_need is not None:
                # reserve the delivery; the pickup at the shed fills the rest
                plans[i] = ["SHED", best]
                self._plan_item[i] = best_need
                claimed.add(best)
                if at_shed:
                    got = self._delivery(pos, inv, pending, claimed - {best}, shed_left, item=best_need)
                    if got:
                        item, n, targets = got
                        actions[i] = ["PICKUP", item, n]
                        shed_left[item] = shed_left.get(item, 0) - n
                        plans[i] = targets
                        claimed.update(targets)
                        continue
                actions[i] = move(pos, nearest_shed(pos))
                continue
            plans[i] = [best]
            self._plan_item[i] = None
            claimed.add(best)
            actions[i] = move(pos, best)
        return actions

    def _zones(self, n_units, pending, unlocked):
        """Home quadrant per unit, in proportion to each quadrant's pending work."""
        if self.cfg["zone_penalty"] <= 0 or len(unlocked) <= 1:
            return None
        work = {q: 0 for q in unlocked}
        for p in pending:
            q = quadrant(*p)
            if q in work:
                work[q] += 1
        total = sum(work.values())
        if total <= 0:
            return None
        zones = [None] * n_units
        quota = {q: work[q] / total * n_units for q in work}
        order = sorted(work, key=lambda q: -work[q])
        k = 0
        for q in order:
            for _ in range(int(round(quota[q]))):
                if k < n_units:
                    zones[k] = q
                    k += 1
        while k < n_units:
            zones[k] = order[k % len(order)]
            k += 1
        return zones

    def _delivery(self, pos, inv, pending, claimed, shed_left, item=None):
        """Pick a supply item and the tiles it will be delivered to."""
        c = self.cfg
        want = {}
        for p, (a, need) in pending.items():
            if need is not None and p not in claimed:
                want.setdefault(need, []).append(p)
        order = (item,) if item else ("COW", "SHEEP", "GOOSE", "WHEAT", "FERTILIZER")
        for it in order:
            tiles = want.get(it, [])
            avail = shed_left.get(it, 0)
            if not tiles or avail <= 0 or inv.get(it, 0) > 0:
                continue
            cap = 1 if it in ("COW", "SHEEP", "GOOSE") else (c["feed_chunk"] if it == "WHEAT" else c["fert_chunk"])
            cap = min(cap, avail)
            route, cur, left = [], pos, list(tiles)
            while left and len(route) < cap:
                nxt = min(left, key=lambda p: dist(cur, p))
                route.append(nxt)
                left.remove(nxt)
                cur = nxt
            return it, len(route), route
        return None

    # ------------------------------------------------------------- market
    def _market(self, obs, farm, shed, seeds, day, hour, shops, pending, n_units, animals, crops):
        c = self.cfg
        orders = []
        incoming = {"COW": 0, "SHEEP": 0, "GOOSE": 0}
        prices = obs["market"]["prices"]
        money = float(farm["money"])
        n_animals = sum(animals.values())
        final_day = day >= DAYS - 1
        wheat_price = prices["WHEAT"] + 1

        reserve_wheat = n_animals * c["wheat_feed_days"] + sum(1 for p, (a, nd) in pending.items() if nd == "WHEAT")
        if final_day:
            reserve_wheat = n_animals if hour < 8 else 0
        fert_jobs = sum(1 for p, (a, nd) in pending.items() if nd == "FERTILIZER")
        sells = self._sells(obs, shed, day, hour, reserve_wheat, fert_jobs)
        orders += sells
        cash = money + self._sale_value(obs, sells)

        # 1) today's hands
        hires = int(farm.get("hires_today", 0))
        want_hands = self._hands_wanted(pending, day, n_animals, crops)
        if day == 0:
            want_hands = c["open_hands"]
        if hour <= 3 and not final_day or (final_day and hour <= 1):
            n_hired = n_units - 1
            while n_hired < want_hands and len(orders) < 9:
                cost = fib_cost(hires)
                if cash < cost:
                    break
                orders.append(["HIRE"])
                cash -= cost
                hires += 1
                n_hired += 1
        # 2) feed for today and tomorrow morning
        wheat_have = shed.get("WHEAT", 0) + sum(inv.get("WHEAT", 0) for inv in obs["private"].get("inventories") or [])
        unfed = sum(1 for p, (a, nd) in pending.items() if nd == "WHEAT")
        waiting = sum(n for a, n in shed.items() if a in ("COW", "SHEEP", "GOOSE"))
        feed_need = unfed + waiting
        if hour >= 20:
            feed_need = n_animals + waiting   # tomorrow morning
        if final_day and hour > 6:
            feed_need = 0
        n = feed_need - wheat_have
        if n > 0 and len(orders) < 10:
            n = int(min(n, cash // wheat_price))
            if n > 0:
                orders.append(["BUY_PRODUCT", "WHEAT", n])
                cash -= n * wheat_price
        # reserve for tomorrow's hands and feed
        reserve = hire_total(min(c["hands_max"], max(want_hands, c["hands_min"]))) + n_animals * wheat_price + c["cash_buffer"]
        free = cash - reserve
        if final_day:
            return orders, incoming
        # 3) land on its planned day takes priority over seeds and animals
        unlocked_n = len(farm["unlocked_quadrants"]) - 1
        if unlocked_n < 3 and day >= c["land_days"][unlocked_n] and len(orders) < 10:
            price = LAND_PRICES[unlocked_n]
            if cash - price >= c["land_reserve"]:
                orders.append(["BUY_LAND"])
                cash -= price
                free -= price
        # 3b) seeds for plantings that can happen today
        need = {}
        for (x, y), role in self.role.items():
            t = farm["tiles"][y][x]
            crop = None
            if t is None:
                crop = self._crop_for((x, y), day, shops, False)
            elif isinstance(t, dict) and t.get("kind") == "PLANT" and t["crop"] in ("WHEAT", "CARROT"):
                if day - t["planted_day"] >= c["wheat_harvest_age"] - (1 if hour >= 18 else 0):
                    crop = self._crop_for((x, y), day + (1 if hour >= 18 else 0), shops, False)
            elif isinstance(t, dict) and t.get("kind") == "WEED" and role not in ("COW", "SHEEP", "GOOSE"):
                crop = self._crop_for((x, y), day, shops, False)
            if crop:
                need[crop] = need.get(crop, 0) + 1
        for crop in ("MELON", "STRAWBERRY", "TOMATO", "CARROT", "WHEAT"):
            n = need.get(crop, 0) - seeds.get(crop, 0)
            if n <= 0 or len(orders) >= 10:
                continue
            cost = CROPS[crop]["seed"]
            budget = free if day > 0 else cash - 60
            n = int(min(n, max(0.0, budget) // cost))
            if n > 0:
                orders.append(["BUY_SEED", crop, n])
                cash -= n * cost
                free -= n * cost
        # 4) animals for waiting pastures
        if day <= c["animal_last_day"]:
            for animal in ("COW", "SHEEP", "GOOSE"):
                roles = self._count_roles(animal)
                have = animals[animal] + shed.get(animal, 0) + sum(
                    inv.get(animal, 0) for inv in obs["private"].get("inventories") or [])
                n = roles - have
                cost = ANIMALS[animal]["cost"]
                budget = free if day > 0 else cash - 250
                while n > 0 and budget >= cost and len(orders) < 10:
                    orders.append(["BUY_ANIMAL", animal, 1])
                    incoming[animal] += 1
                    cash -= cost
                    free -= cost
                    budget -= cost
                    n -= 1
        # 6) cheap fertiliser for pending jobs (never while selling it)
        want_fert = sum(1 for p, (a, nd) in pending.items() if nd == "FERTILIZER")
        selling_fert = any(o[1] == "FERTILIZER" for o in sells)
        if prices["FERTILIZER"] <= c["fert_buy_below"] and not selling_fert and len(orders) < 10:
            n = int(min(want_fert - shed.get("FERTILIZER", 0), free // (prices["FERTILIZER"] + 1)))
            if n > 0:
                orders.append(["BUY_PRODUCT", "FERTILIZER", n])
        return orders, incoming

    def _sells(self, obs, shed, day, hour, reserve_wheat, fert_jobs=0):
        c = self.cfg
        inv = obs["market"]["inventory"]
        orders = []
        final_day = day >= DAYS - 1
        liquidate = final_day and hour >= c["liquidate_hour"]
        shed_total = sum(shed.values())
        fert_keep = 0 if final_day else fert_jobs + c["fert_keep"]
        for item in ("MILK", "WOOL", "STRAWBERRY", "MELON", "WHEAT", "FERTILIZER", "CARROT", "TOMATO", "EGG"):
            have = shed.get(item, 0)
            if item == "WHEAT":
                have -= reserve_wheat
            if item == "FERTILIZER":
                have -= fert_keep
            if have <= 0:
                continue
            if liquidate:
                orders.append(["SELL", item, int(have)])
                continue
            base = MARKET[item][0]
            ratio = c["sell_ratio"].get(item, 0.7)
            if day >= DAYS - 3:
                ratio = min(ratio, c["sell_ratio_late"])
            floor = base * ratio
            n = 0
            cur = inv[item]
            while n < have and price_at(item, cur + n) >= floor:
                n += 1
            # never hoard: stock above the holding cap is sold at market
            n = max(n, have - c["hold_cap"].get(item, 12))
            if shed_total > 75:
                n = max(n, min(have, shed_total - 65))
            if n > 0:
                orders.append(["SELL", item, int(n)])
        return orders

    def _sale_value(self, obs, sells):
        inv = obs["market"]["inventory"]
        total = 0.0
        for _, item, n in sells:
            cur = inv[item]
            for k in range(n):
                total += price_at(item, cur + k)
        return total

    def _hands_wanted(self, pending, day, n_animals, crops):
        c = self.cfg
        want = math.ceil(self.load / (23.0 * c["efficiency"])) - 1
        return int(max(c["hands_min"], min(c["hands_max"], want)))

    def _urgency(self, t, day, step):
        """Extra priority for work that is lost if not done today."""
        if not isinstance(t, dict):
            return 0
        hour = step % TURNS
        late = 3 if hour >= 15 else 0
        if t.get("kind") == "PLANT":
            cd = CROPS[t["crop"]]
            age = day - t["planted_day"]
            if not cd["ongoing"] and age >= cd["max_day"] and t.get("yield_units", 0) > 0:
                return 6 + late
            if not t.get("watered_today") and t.get("consecutive_unwatered", 0) >= 1:
                return 5 + late
            if cd["ongoing"] and t.get("yield_units", 0) >= cd["max_yield"]:
                return 3
            return 0
        if t.get("animal"):
            if not t.get("fed_today") and t.get("consecutive_unfed", 0) >= 1:
                return 6 + late
            if t.get("yield_units", 0) >= 5:
                return 2
        return 0

    def _update_load(self, tiles):
        """Labour the current farm needs per day, in unit-turns."""
        c = self.cfg
        load = 0.0
        for y in range(10):
            for x in range(10):
                t = tiles[y][x]
                if not isinstance(t, dict):
                    continue
                if t.get("animal"):
                    load += c["load_animal"]
                elif t.get("kind") == "PLANT":
                    load += c["load_straw"] if t["crop"] in ("STRAWBERRY", "TOMATO") else (
                        c["load_melon"] if t["crop"] == "MELON" else c["load_fill"])
        self.load = load
        self.capacity = (1 + c["hands_max"]) * 23.0 * c["efficiency"]


_AGENTS = {}


def agent(observation, configuration=None):
    me = int(g(observation, "player", 0))
    step = int(g(observation, "step", 0))
    bot = _AGENTS.get(me)
    if bot is None or step == 0 or step < getattr(bot, "_last_step", -1):
        bot = FQ4()
        _AGENTS[me] = bot
    bot._last_step = step
    try:
        return bot.act(observation)
    except Exception:
        return {"farmer": ["PASS"], "hands": [], "market": []}

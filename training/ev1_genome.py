"""Conditional strategy modules for the 0801_ev1 expansion-policy engine."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import random
from typing import Any


STRATEGY_FAMILIES = ("ev1", "fertilized", "high_labor", "full_land", "adaptive")
CROP_SYSTEMS = ("ev1", "berry", "balanced", "market")
HERD_SYSTEMS = ("ev1", "balanced", "cow", "sheep", "market")
FERTILIZER_SYSTEMS = ("sell", "strawberry", "ongoing", "all")


@dataclass(frozen=True)
class Ev1Genome:
    strategy_family: str = "ev1"
    crop_system: str = "ev1"
    crop_cells: int = 25
    core_melons: int = 11
    core_carrots: int = 2
    wheat_per_quadrant: int = 4
    strawberry_bias: int = 0
    max_quadrants: int = 3
    first_land_day: int = 5
    second_land_day: int = 9
    third_land_day: int = 15
    first_land_buffer: int = 300
    later_land_buffer: int = 500
    target_hands: int = 10
    herd_system: str = "ev1"
    opening_cows: int = 2
    opening_sheep: int = 2
    first_herd_day: int = 7
    final_herd_day: int = 11
    herd_size: int = 12
    first_herd_size: int = 8
    market_ratio: float = 1.03
    wheat_per_animal: int = 3
    wheat_buffer: int = 3
    animal_purchase_batch: int = 2
    fertilizer_system: str = "sell"
    fertilizer_priority: int = 4
    fertilizer_refresh: int = 0
    ongoing_harvest: int = 3

    def normalized(self) -> "Ev1Genome":
        values = asdict(self)
        values["strategy_family"] = _choice(values["strategy_family"], STRATEGY_FAMILIES)
        values["crop_system"] = _choice(values["crop_system"], CROP_SYSTEMS)
        values["herd_system"] = _choice(values["herd_system"], HERD_SYSTEMS)
        values["fertilizer_system"] = _choice(
            values["fertilizer_system"], FERTILIZER_SYSTEMS
        )
        values["crop_cells"] = _clip_int(values["crop_cells"], 14, 25)
        values["core_melons"] = _clip_int(values["core_melons"], 0, 16)
        values["core_carrots"] = _clip_int(values["core_carrots"], 0, 6)
        values["wheat_per_quadrant"] = _clip_int(
            values["wheat_per_quadrant"], 0, 8
        )
        values["strawberry_bias"] = _clip_int(values["strawberry_bias"], -6, 8)
        values["max_quadrants"] = _clip_int(values["max_quadrants"], 1, 4)
        values["first_land_day"] = _clip_int(values["first_land_day"], 2, 10)
        values["second_land_day"] = _clip_int(
            values["second_land_day"], values["first_land_day"] + 1, 16
        )
        values["third_land_day"] = _clip_int(
            values["third_land_day"], values["second_land_day"] + 1, 22
        )
        values["first_land_buffer"] = _clip_int(values["first_land_buffer"], 0, 1200)
        values["later_land_buffer"] = _clip_int(values["later_land_buffer"], 0, 1800)
        values["target_hands"] = _clip_int(values["target_hands"], 6, 15)
        values["opening_cows"] = _clip_int(values["opening_cows"], 0, 4)
        values["opening_sheep"] = _clip_int(values["opening_sheep"], 0, 4)
        values["first_herd_day"] = _clip_int(values["first_herd_day"], 4, 12)
        values["final_herd_day"] = _clip_int(
            values["final_herd_day"], values["first_herd_day"] + 1, 18
        )
        values["herd_size"] = _clip_int(values["herd_size"], 0, 20)
        values["first_herd_size"] = _clip_int(
            values["first_herd_size"],
            values["opening_cows"] + values["opening_sheep"],
            values["herd_size"],
        )
        values["market_ratio"] = round(
            max(0.90, min(1.15, float(values["market_ratio"]))), 3
        )
        values["wheat_per_animal"] = _clip_int(values["wheat_per_animal"], 1, 5)
        values["wheat_buffer"] = _clip_int(values["wheat_buffer"], 0, 12)
        values["animal_purchase_batch"] = _clip_int(
            values["animal_purchase_batch"], 1, 6
        )
        values["fertilizer_priority"] = _clip_int(
            values["fertilizer_priority"], 0, 9
        )
        values["fertilizer_refresh"] = _clip_int(values["fertilizer_refresh"], 0, 3)
        values["ongoing_harvest"] = _clip_int(values["ongoing_harvest"], 1, 4)
        return Ev1Genome(**values)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self.normalized())

    def key(self) -> str:
        values = self.to_dict()
        active = active_field_names(self)
        defaults = Ev1Genome().to_dict()
        for name in values:
            if name not in active:
                values[name] = defaults[name]
        return "|".join(f"{name}={values[name]}" for name in values)


def _choice(value: Any, choices: tuple[str, ...]) -> str:
    return str(value) if str(value) in choices else choices[0]


def _clip_int(value: Any, low: int, high: int) -> int:
    return max(low, min(high, int(value)))


def active_field_names(genome: Ev1Genome) -> set[str]:
    genome = genome.normalized()
    active = {
        "strategy_family", "crop_system", "crop_cells", "core_melons",
        "core_carrots", "wheat_per_quadrant", "strawberry_bias",
        "max_quadrants", "target_hands", "herd_system", "opening_cows",
        "opening_sheep", "first_herd_day", "final_herd_day", "herd_size",
        "first_herd_size", "wheat_per_animal", "wheat_buffer",
        "animal_purchase_batch", "fertilizer_system", "ongoing_harvest",
    }
    if genome.max_quadrants >= 2:
        active.update(("first_land_day", "first_land_buffer"))
    if genome.max_quadrants >= 3:
        active.update(("second_land_day", "later_land_buffer"))
    if genome.max_quadrants >= 4:
        active.add("third_land_day")
    if genome.herd_system == "market":
        active.add("market_ratio")
    if genome.fertilizer_system != "sell":
        active.update(("fertilizer_priority", "fertilizer_refresh"))
    return active


FIELD_CHOICES: dict[str, tuple[Any, ...]] = {
    "strategy_family": STRATEGY_FAMILIES,
    "crop_system": CROP_SYSTEMS,
    "crop_cells": tuple(range(14, 26)),
    "core_melons": tuple(range(0, 17)),
    "core_carrots": tuple(range(0, 7)),
    "wheat_per_quadrant": tuple(range(0, 9)),
    "strawberry_bias": tuple(range(-6, 9)),
    "max_quadrants": (1, 2, 3, 4),
    "first_land_day": tuple(range(2, 11)),
    "second_land_day": tuple(range(4, 17)),
    "third_land_day": tuple(range(6, 23)),
    "first_land_buffer": tuple(range(0, 1201, 100)),
    "later_land_buffer": tuple(range(0, 1801, 100)),
    "target_hands": tuple(range(6, 16)),
    "herd_system": HERD_SYSTEMS,
    "opening_cows": tuple(range(0, 5)),
    "opening_sheep": tuple(range(0, 5)),
    "first_herd_day": tuple(range(4, 13)),
    "final_herd_day": tuple(range(6, 19)),
    "herd_size": tuple(range(0, 21)),
    "first_herd_size": tuple(range(0, 21)),
    "market_ratio": tuple(round(0.90 + 0.01 * index, 2) for index in range(26)),
    "wheat_per_animal": (1, 2, 3, 4, 5),
    "wheat_buffer": tuple(range(0, 13)),
    "animal_purchase_batch": (1, 2, 3, 4, 5, 6),
    "fertilizer_system": FERTILIZER_SYSTEMS,
    "fertilizer_priority": tuple(range(0, 10)),
    "fertilizer_refresh": (0, 1, 2, 3),
    "ongoing_harvest": (1, 2, 3, 4),
}


GENE_BLOCKS = {
    "crops": (
        "crop_system", "crop_cells", "core_melons", "core_carrots",
        "wheat_per_quadrant", "strawberry_bias", "ongoing_harvest",
    ),
    "expansion": (
        "max_quadrants", "first_land_day", "second_land_day", "third_land_day",
        "first_land_buffer", "later_land_buffer", "target_hands",
    ),
    "herd": (
        "herd_system", "opening_cows", "opening_sheep", "first_herd_day",
        "final_herd_day", "herd_size", "first_herd_size", "market_ratio",
        "wheat_per_animal", "wheat_buffer", "animal_purchase_batch",
    ),
    "fertilizer": (
        "fertilizer_system", "fertilizer_priority", "fertilizer_refresh",
    ),
}


def family_seed_genomes(base: Ev1Genome | None = None) -> list[Ev1Genome]:
    base = (base or Ev1Genome()).normalized()
    return [
        replace(base, strategy_family="ev1"),
        replace(
            base, strategy_family="fertilized", fertilizer_system="strawberry",
            fertilizer_priority=3, target_hands=max(11, base.target_hands),
        ).normalized(),
        replace(
            base, strategy_family="high_labor", target_hands=13,
            crop_cells=25, crop_system="berry",
        ).normalized(),
        replace(
            base, strategy_family="full_land", max_quadrants=4,
            target_hands=14, third_land_day=14, crop_system="berry",
        ).normalized(),
        replace(
            base, strategy_family="adaptive", crop_system="market",
            herd_system="market", fertilizer_system="ongoing",
            target_hands=12,
        ).normalized(),
    ]


def mutate(genome: Ev1Genome, rng: random.Random, changes: int | None = None) -> Ev1Genome:
    genome = genome.normalized()
    if rng.random() < 0.12:
        anchors = family_seed_genomes(genome)
        return rng.choice(anchors).normalized()
    values = genome.to_dict()
    active = active_field_names(genome) - {"strategy_family"}
    if changes is None:
        changes = 2 if rng.random() < 0.60 else 1
    if rng.random() < 0.65:
        block = rng.choice(tuple(GENE_BLOCKS.values()))
        candidates = [name for name in block if name in active]
    else:
        candidates = list(active)
    rng.shuffle(candidates)
    for name in candidates[:changes]:
        choices = [value for value in FIELD_CHOICES[name] if value != values[name]]
        if choices:
            values[name] = rng.choice(choices)
    return Ev1Genome(**values).normalized()


def crossover(first: Ev1Genome, second: Ev1Genome, rng: random.Random) -> Ev1Genome:
    a, b = first.to_dict(), second.to_dict()
    child = dict(a)
    for block in GENE_BLOCKS.values():
        source = b if rng.random() < 0.5 else a
        for name in block:
            child[name] = source[name]
    child["strategy_family"] = rng.choice(
        (a["strategy_family"], b["strategy_family"])
    )
    return Ev1Genome(**child).normalized()


def configure_module(module: Any, genome: Ev1Genome):
    """Install structural policy modules onto a freshly loaded 0801_ev1 module."""
    genome = genome.normalized()
    original_agent = module.agent
    original_crop_tasks = module._crop_tasks
    original_market_actions = module._market_actions
    state: dict[str, Any] = {"prices": {}, "target": None}

    def animal_slots(board_size: int, unlocked_quadrants: list[str]):
        h = board_size // 2
        quadrants = set(unlocked_quadrants or ["NW"])
        slots = [
            (h - 1, h - 1), (h - 2, h - 1), (h - 1, h - 2), (h - 1, h - 3),
        ]
        if "NE" in quadrants:
            slots.extend(
                [(h, h - 1), (h, h - 2), (h + 1, h - 3), (h + 2, h - 2)]
            )
        if "SW" in quadrants:
            slots.extend([(h - 2, h), (h - 1, h), (h - 1, h + 1), (h - 2, h + 1)])
        if "SE" in quadrants:
            slots.extend([(h, h), (h + 1, h), (h, h + 1), (h + 1, h + 1)])
        return [
            position for position in slots[: genome.herd_size]
            if 0 <= position[0] < board_size and 0 <= position[1] < board_size
        ]

    def crop_mix(quadrant: str, cell_count: int) -> list[str]:
        prices = state["prices"]
        wheat = min(genome.wheat_per_quadrant, cell_count)
        carrots = genome.core_carrots if quadrant == "NW" else 1
        melons = genome.core_melons if quadrant == "NW" else 0
        if genome.crop_system == "berry":
            melons = max(0, melons - 4)
            carrots = max(0, carrots - 1)
        elif genome.crop_system == "balanced":
            melons = max(melons, 6 if quadrant == "NW" else 2)
        elif genome.crop_system == "market":
            strawberry_value = float(prices.get("STRAWBERRY", 120)) / 2.0
            melon_value = float(prices.get("MELON", 250)) / 12.0
            if melon_value > strawberry_value:
                melons = max(melons, 10 if quadrant == "NW" else 5)
            else:
                melons = max(0, melons - 4)
        berries = max(0, cell_count - wheat - carrots - melons + genome.strawberry_bias)
        crops = ["MELON"] * melons + ["STRAWBERRY"] * berries
        crops += ["CARROT"] * carrots + ["WHEAT"] * wheat
        return crops[:cell_count]

    def crop_plan(board_size: int, unlocked_quadrants: list[str], excluded: set[tuple[int, int]]):
        h = board_size // 2
        shed = (h - 1, h - 1)
        bounds = {
            "NW": (range(0, h), range(0, h)),
            "NE": (range(h, board_size), range(0, h)),
            "SW": (range(0, h), range(h, board_size)),
            "SE": (range(h, board_size), range(h, board_size)),
        }
        plan: dict[tuple[int, int], str] = {}
        for quadrant in ("NW", "NE", "SW", "SE"):
            if quadrant not in set(unlocked_quadrants or ["NW"]):
                continue
            xs, ys = bounds[quadrant]
            cells = [(x, y) for y in ys for x in xs if (x, y) not in excluded]
            cells.sort(key=lambda position: (module._dist(position, shed), position[1], position[0]))
            cells = cells[: genome.crop_cells]
            crops = crop_mix(quadrant, len(cells))
            crops.extend(["STRAWBERRY"] * (len(cells) - len(crops)))
            plan.update(zip(cells, crops))
        return plan

    def top_target(obs: dict[str, Any], expanded: bool):
        day = int(obs.get("day", 0))
        opening = {"COW": genome.opening_cows, "SHEEP": genome.opening_sheep}
        if not expanded or day < genome.first_herd_day:
            state["target"] = opening
            return opening
        size = genome.first_herd_size if day < genome.final_herd_day else genome.herd_size
        if genome.herd_system == "cow":
            sheep = min(genome.opening_sheep, size)
            target = {"COW": size - sheep, "SHEEP": sheep}
        elif genome.herd_system == "sheep":
            cows = min(genome.opening_cows, size)
            target = {"COW": cows, "SHEEP": size - cows}
        elif genome.herd_system == "balanced":
            target = {"COW": (size + 1) // 2, "SHEEP": size // 2}
        else:
            prices = ((obs.get("market", {}) or {}).get("prices", {}) or {})
            milk = float(prices.get("MILK", 160))
            wool = float(prices.get("WOOL", 200))
            ratio = genome.market_ratio if genome.herd_system == "market" else 1.03
            if milk > ratio * wool:
                target = {"COW": size - genome.opening_sheep, "SHEEP": genome.opening_sheep}
            elif wool > ratio * milk:
                target = {"COW": genome.opening_cows, "SHEEP": size - genome.opening_cows}
            else:
                target = {"COW": (size + 1) // 2, "SHEEP": size // 2}
        state["target"] = target
        return target

    def crop_tasks(obs, farm, private, plan, animal_positions):
        tasks = original_crop_tasks(obs, farm, private, plan, animal_positions)
        day = int(obs.get("day", 0))
        if genome.ongoing_harvest != 3:
            filtered = []
            for task in tasks:
                x, y = task["pos"]
                tile = farm["tiles"][y][x]
                if (
                    task["action"] == ["HARVEST"]
                    and isinstance(tile, dict)
                    and module.CROP_RULES.get(tile.get("crop"), (0, 0, 0, 0, False))[4]
                    and int(tile.get("yield_units", 0)) < genome.ongoing_harvest
                    and day < 27
                ):
                    continue
                filtered.append(task)
            tasks = filtered
            if genome.ongoing_harvest < 3:
                occupied = {tuple(task["pos"]) for task in tasks if task["action"] == ["HARVEST"]}
                for position, planned in plan.items():
                    if position in animal_positions or position in occupied:
                        continue
                    x, y = position
                    tile = farm["tiles"][y][x]
                    if not isinstance(tile, dict) or tile.get("kind") != "PLANT":
                        continue
                    crop = tile.get("crop", planned)
                    rule = module.CROP_RULES.get(crop, module.CROP_RULES[planned])
                    age = day - int(tile.get("planted_day", day))
                    if rule[4] and age >= rule[1] and int(tile.get("yield_units", 0)) >= genome.ongoing_harvest:
                        module._add(tasks, 4, position, ["HARVEST"])

        if genome.fertilizer_system != "sell" and module._total(private, "FERTILIZER") > 0:
            for position, planned in plan.items():
                if position in animal_positions:
                    continue
                x, y = position
                tile = farm["tiles"][y][x]
                if not isinstance(tile, dict) or tile.get("kind") != "PLANT":
                    continue
                crop = tile.get("crop", planned)
                eligible = (
                    genome.fertilizer_system == "all"
                    or genome.fertilizer_system == "strawberry" and crop == "STRAWBERRY"
                    or genome.fertilizer_system == "ongoing" and module.CROP_RULES[crop][4]
                )
                if eligible and int(tile.get("fertilized_until_day", -1)) <= day + genome.fertilizer_refresh:
                    module._add(
                        tasks, genome.fertilizer_priority, position,
                        ["FERTILIZE"], "FERTILIZER",
                    )
        return tasks

    def estimated_budget(farm, private, orders, prices) -> float:
        budget = float(farm.get("money", 0))
        shed = private.get("shed", {}) or {}
        for order in orders:
            if len(order) < 3:
                continue
            operation, item, amount = order[:3]
            amount = int(amount)
            if operation == "SELL":
                budget += min(amount, int(shed.get(item, 0))) * int(prices.get(item, 1))
            elif operation == "BUY_SEED":
                budget -= amount * module.CROP_RULES[item][0]
            elif operation == "BUY_PRODUCT":
                budget -= amount * int(prices.get(item, 1))
            elif operation == "BUY_ANIMAL":
                budget -= amount * (400 if item == "COW" else 500)
        return budget

    def market_actions(obs, farm, private, animal_positions, plan):
        orders = original_market_actions(obs, farm, private, animal_positions, plan)
        day = int(obs.get("day", 0))
        hour = int(obs.get("hour", 0))
        prices = ((obs.get("market", {}) or {}).get("prices", {}) or {})
        if genome.fertilizer_system != "sell":
            orders = [
                order for order in orders
                if not (len(order) >= 2 and order[0] == "SELL" and order[1] == "FERTILIZER")
            ]
        quadrants = len(farm.get("unlocked_quadrants", []) or ["NW"])
        land_days = (genome.first_land_day, genome.second_land_day, genome.third_land_day)
        land_buffers = (
            genome.first_land_buffer, genome.later_land_buffer, genome.later_land_buffer,
        )
        filtered = []
        for order in orders:
            if order and order[0] == "BUY_LAND":
                index = max(0, quadrants - 1)
                if quadrants >= genome.max_quadrants or day < land_days[index]:
                    continue
            if order and order[0] == "HIRE":
                continue
            filtered.append(order)
        orders = filtered[:10]
        budget = estimated_budget(farm, private, orders, prices)
        if (
            day < 29 and quadrants < genome.max_quadrants
            and day >= land_days[quadrants - 1]
            and not any(order and order[0] == "BUY_LAND" for order in orders)
        ):
            cost = (1000, 2000, 4000)[quadrants - 1]
            if budget >= cost + land_buffers[quadrants - 1] and len(orders) < 10:
                orders.append(["BUY_LAND"])
                budget -= cost
        if hour <= 3:
            missing = max(0, genome.target_hands - len(farm.get("hands", []) or []))
            while missing > 0 and len(orders) < 10:
                orders.append(["HIRE"])
                missing -= 1
        return orders[:10]

    module._animal_slots = animal_slots
    module._crop_plan = crop_plan
    module._top_target = top_target
    module._crop_tasks = crop_tasks
    module._market_actions = market_actions

    def agent(obs: dict[str, Any]):
        day = int(obs.get("day", 0))
        hour = int(obs.get("hour", 0))
        if day == 0 and hour == 0:
            state["target"] = None
        state["prices"] = dict(((obs.get("market", {}) or {}).get("prices", {}) or {}))
        return original_agent(obs)

    return agent

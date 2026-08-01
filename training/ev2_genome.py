"""Hierarchical search space for the strong ``test/0801_ev2`` policy.

Only values that are actually read by the policy are exposed.  The old flat
genome contained inactive genes and crossed unrelated policy families; this
space keeps economic decisions in coherent blocks and uses ev2 itself as the
zero-change anchor.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import random
from typing import Any


FAMILIES = (
    "ev2", "production", "livestock", "expansion", "fertilized", "realize",
)
QUADRANTS = ("NW", "NE", "SW", "SE")
PRODUCTS = (
    "WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON",
    "EGG", "MILK", "WOOL", "FERTILIZER",
)


@dataclass(frozen=True)
class Ev2Genome:
    # ``family`` selects a mutation neighbourhood, not a hidden behavior flag.
    # It is deliberately omitted from key(), so identical policies deduplicate.
    family: str = "ev2"

    max_hands: int = 12
    liquidation_turns: int = 38
    travel_cost: float = 8.0

    core_herd: int = 4
    mid_herd: int = 8
    target_herd: int = 12
    herd_expansion_day: int = 7
    herd_final_day: int = 11
    animal_purchase_last_day: int = 18
    feed_stock_days: int = 3

    animal_slots_nw: int = 4
    animal_slots_ne: int = 5
    animal_slots_sw: int = 3
    animal_slots_se: int = 0

    wheat_nw: int = 4
    carrot_nw: int = 2
    wheat_ne: int = 4
    carrot_ne: int = 1
    melon_ne: int = 0
    wheat_sw: int = 4
    carrot_sw: int = 1
    melon_sw: int = 0
    wheat_se: int = 5
    carrot_se: int = 2
    melon_se: int = 0
    melon_tiles_min: int = 8
    melon_tiles_base: int = 10
    melon_tiles_max: int = 12

    max_extra_land: int = 2
    first_land_day: int = 5
    second_land_day: int = 9
    third_land_day: int = 14

    reserve_wheat: float = 0.68
    reserve_carrot: float = 0.55
    reserve_tomato: float = 0.50
    reserve_strawberry: float = 0.48
    reserve_melon: float = 0.58
    reserve_egg: float = 0.65
    reserve_milk: float = 0.42
    reserve_wool: float = 0.40
    reserve_fertilizer: float = 0.18
    fertilizer_use: int = 0
    fertilizer_min_gain: int = 35
    fertilizer_max_jobs: int = 2
    fertilizer_priority: int = 2

    def normalized(self) -> "Ev2Genome":
        values = asdict(self)
        values["family"] = (
            str(values["family"]) if str(values["family"]) in FAMILIES else "ev2"
        )
        values["max_hands"] = _clip_int(values["max_hands"], 8, 16)
        values["liquidation_turns"] = _clip_int(values["liquidation_turns"], 18, 84)
        values["travel_cost"] = _clip_float(values["travel_cost"], 3.0, 16.0, 1)

        values["core_herd"] = _clip_int(values["core_herd"], 2, 8)
        values["mid_herd"] = _clip_int(
            values["mid_herd"], values["core_herd"], 14
        )
        values["target_herd"] = _clip_int(
            values["target_herd"], values["mid_herd"], 20
        )
        values["herd_expansion_day"] = _clip_int(
            values["herd_expansion_day"], 4, 12
        )
        values["herd_final_day"] = _clip_int(
            values["herd_final_day"], values["herd_expansion_day"] + 1, 18
        )
        values["animal_purchase_last_day"] = _clip_int(
            values["animal_purchase_last_day"], values["herd_final_day"], 23
        )
        values["feed_stock_days"] = _clip_int(values["feed_stock_days"], 1, 6)

        for quadrant in ("nw", "ne", "sw", "se"):
            values[f"animal_slots_{quadrant}"] = _clip_int(
                values[f"animal_slots_{quadrant}"], 0, 8
            )
            values[f"wheat_{quadrant}"] = _clip_int(
                values[f"wheat_{quadrant}"], 0, 14
            )
            values[f"carrot_{quadrant}"] = _clip_int(
                values[f"carrot_{quadrant}"], 0, 6
            )
        for quadrant in ("ne", "sw", "se"):
            values[f"melon_{quadrant}"] = _clip_int(
                values[f"melon_{quadrant}"], 0, 10
            )

        values["melon_tiles_min"] = _clip_int(values["melon_tiles_min"], 2, 16)
        values["melon_tiles_base"] = _clip_int(
            values["melon_tiles_base"], values["melon_tiles_min"], 18
        )
        values["melon_tiles_max"] = _clip_int(
            values["melon_tiles_max"], values["melon_tiles_base"], 20
        )
        values["max_extra_land"] = _clip_int(values["max_extra_land"], 0, 3)
        values["first_land_day"] = _clip_int(values["first_land_day"], 2, 12)
        values["second_land_day"] = _clip_int(
            values["second_land_day"], values["first_land_day"] + 1, 18
        )
        values["third_land_day"] = _clip_int(
            values["third_land_day"], values["second_land_day"] + 1, 23
        )
        for product in PRODUCTS:
            field = f"reserve_{product.lower()}"
            values[field] = _clip_float(values[field], 0.05, 0.95, 2)
        values["fertilizer_use"] = _clip_int(values["fertilizer_use"], 0, 1)
        values["fertilizer_min_gain"] = _clip_int(
            values["fertilizer_min_gain"], 0, 160
        )
        values["fertilizer_max_jobs"] = _clip_int(
            values["fertilizer_max_jobs"], 1, 5
        )
        values["fertilizer_priority"] = _clip_int(
            values["fertilizer_priority"], 1, 4
        )
        return Ev2Genome(**values)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self.normalized())

    def phenotype(self) -> dict[str, Any]:
        values = self.to_dict()
        values.pop("family", None)
        if values["max_extra_land"] == 0:
            values["first_land_day"] = Ev2Genome.first_land_day
            values["second_land_day"] = Ev2Genome.second_land_day
            values["third_land_day"] = Ev2Genome.third_land_day
        elif values["max_extra_land"] == 1:
            values["second_land_day"] = Ev2Genome.second_land_day
            values["third_land_day"] = Ev2Genome.third_land_day
        elif values["max_extra_land"] == 2:
            values["third_land_day"] = Ev2Genome.third_land_day
        if not values["fertilizer_use"]:
            values["fertilizer_min_gain"] = Ev2Genome.fertilizer_min_gain
            values["fertilizer_max_jobs"] = Ev2Genome.fertilizer_max_jobs
            values["fertilizer_priority"] = Ev2Genome.fertilizer_priority
        return values

    def key(self) -> str:
        return "|".join(f"{name}={value}" for name, value in self.phenotype().items())


def _clip_int(value: Any, low: int, high: int) -> int:
    if high < low:
        high = low
    return max(low, min(high, int(value)))


def _clip_float(value: Any, low: float, high: float, digits: int) -> float:
    return round(max(low, min(high, float(value))), digits)


GENE_BLOCKS: dict[str, tuple[str, ...]] = {
    "labor": ("max_hands", "liquidation_turns", "travel_cost"),
    "herd_timing": (
        "core_herd", "mid_herd", "target_herd", "herd_expansion_day",
        "herd_final_day", "animal_purchase_last_day", "feed_stock_days",
    ),
    "animal_layout": (
        "animal_slots_nw", "animal_slots_ne", "animal_slots_sw",
        "animal_slots_se",
    ),
    "crop_layout": (
        "wheat_nw", "carrot_nw", "wheat_ne", "carrot_ne", "melon_ne",
        "wheat_sw", "carrot_sw", "melon_sw", "wheat_se", "carrot_se",
        "melon_se", "melon_tiles_min", "melon_tiles_base", "melon_tiles_max",
    ),
    "expansion": (
        "max_extra_land", "first_land_day", "second_land_day", "third_land_day",
    ),
    "crop_sales": (
        "reserve_wheat", "reserve_carrot", "reserve_tomato",
        "reserve_strawberry", "reserve_melon",
    ),
    "animal_sales": ("reserve_egg", "reserve_milk", "reserve_wool"),
    "fertilizer": (
        "reserve_fertilizer", "fertilizer_use", "fertilizer_min_gain",
        "fertilizer_max_jobs", "fertilizer_priority",
    ),
}


FIELD_STEPS: dict[str, tuple[float, float]] = {
    "max_hands": (1, 2),
    "liquidation_turns": (4, 10),
    "travel_cost": (1.0, 2.5),
    "core_herd": (1, 2),
    "mid_herd": (1, 2),
    "target_herd": (1, 3),
    "herd_expansion_day": (1, 2),
    "herd_final_day": (1, 3),
    "animal_purchase_last_day": (1, 3),
    "feed_stock_days": (1, 2),
    "max_extra_land": (1, 1),
    "first_land_day": (1, 2),
    "second_land_day": (1, 3),
    "third_land_day": (1, 3),
    "melon_tiles_min": (1, 3),
    "melon_tiles_base": (1, 3),
    "melon_tiles_max": (1, 3),
}
for prefix in ("animal_slots", "wheat", "carrot", "melon"):
    for quadrant in ("nw", "ne", "sw", "se"):
        FIELD_STEPS.setdefault(f"{prefix}_{quadrant}", (1, 2))
for product in PRODUCTS:
    FIELD_STEPS[f"reserve_{product.lower()}"] = (0.04, 0.10)
FIELD_STEPS.update(
    {
        "fertilizer_use": (1, 1),
        "fertilizer_min_gain": (10, 30),
        "fertilizer_max_jobs": (1, 2),
        "fertilizer_priority": (1, 1),
    }
)


def family_seed_genomes(base: Ev2Genome | None = None) -> list[Ev2Genome]:
    base = (base or Ev2Genome()).normalized()
    return [
        replace(base, family="ev2").normalized(),
        replace(
            base, family="production", max_hands=14, target_herd=10,
            wheat_ne=3, wheat_sw=3, wheat_se=4, max_extra_land=3,
            second_land_day=8,
        ).normalized(),
        replace(
            base, family="livestock", max_hands=14, mid_herd=10,
            target_herd=15, feed_stock_days=4, animal_slots_sw=5,
            animal_slots_se=2,
        ).normalized(),
        replace(
            base, family="expansion", max_hands=15, max_extra_land=3,
            first_land_day=4, second_land_day=7, target_herd=13,
        ).normalized(),
        replace(
            base, family="fertilized", fertilizer_use=1,
            fertilizer_min_gain=35, fertilizer_max_jobs=2,
            reserve_fertilizer=0.08,
        ).normalized(),
        replace(
            base, family="realize", liquidation_turns=54,
            reserve_strawberry=0.38, reserve_melon=0.45,
            reserve_milk=0.34, reserve_wool=0.32,
        ).normalized(),
    ]


FAMILY_BLOCKS = {
    "ev2": tuple(GENE_BLOCKS),
    "production": ("labor", "crop_layout", "expansion", "crop_sales"),
    "livestock": ("labor", "herd_timing", "animal_layout", "animal_sales"),
    "expansion": ("labor", "animal_layout", "crop_layout", "expansion"),
    "fertilized": ("labor", "crop_layout", "fertilizer"),
    "realize": ("labor", "crop_sales", "animal_sales", "fertilizer"),
}


def mutate(
    genome: Ev2Genome,
    rng: random.Random,
    block: str | None = None,
    changes: int | None = None,
) -> Ev2Genome:
    genome = genome.normalized()
    if rng.random() < 0.07:
        return rng.choice(family_seed_genomes(genome)).normalized()
    values = genome.to_dict()
    eligible = FAMILY_BLOCKS[genome.family]
    block = block if block in eligible else rng.choice(eligible)
    fields = list(GENE_BLOCKS[block])
    rng.shuffle(fields)
    changes = changes or (1 if rng.random() < 0.60 else 2)
    for field in fields[:changes]:
        small, large = FIELD_STEPS[field]
        step = small if rng.random() < 0.80 else large
        if rng.random() < 0.5:
            step = -step
        current = values[field]
        values[field] = current + step
        if isinstance(current, int):
            values[field] = int(round(values[field]))
    return Ev2Genome(**values).normalized()


def crossover(first: Ev2Genome, second: Ev2Genome, rng: random.Random) -> Ev2Genome:
    """Cross only coherent blocks inside the ev2 engine."""
    a, b = first.to_dict(), second.to_dict()
    child = dict(a)
    for block, fields in GENE_BLOCKS.items():
        source = b if rng.random() < 0.5 else a
        for field in fields:
            child[field] = source[field]
    child["family"] = rng.choice((a["family"], b["family"]))
    return Ev2Genome(**child).normalized()


def fertilizer_gain(obs: dict[str, Any], tile: Any, minimum: int = 35) -> float:
    """Conservative value estimate copied from the profitable ev3 module."""
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
        active = sum(
            1 for future_age in (age, age + 1, age + 2)
            if 6 <= future_age <= 12
        )
        bonus_units = min(max(0, 6 - held), active)
    elif crop == "STRAWBERRY" and age >= 8:
        for offset in (0, 1, 2):
            since_first = day + offset + 1 - planted - 10
            if since_first >= 0 and since_first % 2 == 0:
                production_index = since_first // 2 + 1
                if production_index <= 4:
                    bonus_units += 1
    gain = bonus_units * crop_price - fertilizer_price
    return gain if gain >= minimum else 0.0


def install_fertilizer_module(module: Any, genome: Ev2Genome) -> None:
    original_field_jobs = module._field_jobs
    original_unit_actions = module._unit_actions

    def field_jobs(obs, farm, private, roles, liquidation):
        jobs = original_field_jobs(obs, farm, private, roles, liquidation)
        day = int(obs.get("day", 0) or 0)
        hour = int(obs.get("hour", 0) or 0)
        stock = int((private.get("shed", {}) or {}).get("FERTILIZER", 0) or 0)
        stock += sum(
            int((inventory or {}).get("FERTILIZER", 0) or 0)
            for inventory in private.get("inventories", []) or []
        )
        if liquidation or stock <= 0 or day >= 27 or hour > 17:
            return jobs
        urgent_targets = {
            tuple(job["target"])
            for job in jobs
            if int(job.get("priority", 9)) <= 1
        }
        candidates = []
        tiles = farm.get("tiles", []) or []
        for target, role in roles.items():
            if role[0] != "CROP" or tuple(target) in urgent_targets:
                continue
            x, y = target
            tile = tiles[y][x]
            if (
                not isinstance(tile, dict)
                or int(tile.get("consecutive_unwatered", 0) or 0) >= 1
            ):
                continue
            gain = fertilizer_gain(obs, tile, genome.fertilizer_min_gain)
            if gain > 0:
                candidates.append((gain, tuple(target)))
        limit = min(stock, genome.fertilizer_max_jobs)
        for gain, target in sorted(
            candidates, key=lambda pair: (-pair[0], pair[1][1], pair[1][0])
        )[:limit]:
            module._add_job(
                jobs,
                genome.fertilizer_priority,
                gain,
                target,
                ("FERTILIZE",),
                need="FERTILIZER",
                reason="profitable_fertilizer",
                latest_hour=17,
            )
        return jobs

    def unit_actions(obs, config, farm, private, roles):
        result = original_unit_actions(obs, config, farm, private, roles)
        shed_stock = int(
            (private.get("shed", {}) or {}).get("FERTILIZER", 0) or 0
        )
        carried = sum(
            int((inventory or {}).get("FERTILIZER", 0) or 0)
            for inventory in private.get("inventories", []) or []
        )
        if shed_stock <= 0 or carried > 0:
            return result
        jobs = field_jobs(obs, farm, private, roles, liquidation=False)
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
            shed = module._nearest_shed(position, board_size, tiles)
            options.append((module._distance(position, shed), index, shed))
        if not options:
            return result
        _, index, shed = min(options)
        position = positions[index]
        action = (
            ["PICKUP", "FERTILIZER", 1]
            if tuple(position) == tuple(shed)
            else module._bfs_first_step(tiles, position, shed)
        )
        if index == 0:
            result["farmer"] = action
        else:
            result["hands"][index - 1] = action
        return result

    module._field_jobs = field_jobs
    module._unit_actions = unit_actions


def configure_module(module: Any, genome: Ev2Genome):
    """Apply a genome to a freshly imported 0801_ev2 module."""
    genome = genome.normalized()
    module.MAX_HANDS = genome.max_hands
    module.LIQUIDATION_TURNS = genome.liquidation_turns
    module.TRAVEL_COST = genome.travel_cost
    module.CORE_HERD = genome.core_herd
    module.MID_HERD = genome.mid_herd
    module.TARGET_HERD = genome.target_herd
    module.HERD_EXPANSION_DAY = genome.herd_expansion_day
    module.HERD_FINAL_DAY = genome.herd_final_day
    module.ANIMAL_PURCHASE_LAST_DAY = genome.animal_purchase_last_day
    module.FEED_STOCK_DAYS = genome.feed_stock_days
    module.ANIMAL_SLOTS = {
        quadrant: getattr(genome, f"animal_slots_{quadrant.lower()}")
        for quadrant in QUADRANTS
    }
    module.CROP_MIX = {
        "NW": {"MELON": genome.melon_tiles_base, "WHEAT": genome.wheat_nw,
               "CARROT": genome.carrot_nw},
        "NE": {"MELON": genome.melon_ne, "WHEAT": genome.wheat_ne,
               "CARROT": genome.carrot_ne},
        "SW": {"MELON": genome.melon_sw, "WHEAT": genome.wheat_sw,
               "CARROT": genome.carrot_sw},
        "SE": {"MELON": genome.melon_se, "WHEAT": genome.wheat_se,
               "CARROT": genome.carrot_se},
    }
    module.MELON_TILES_MIN = genome.melon_tiles_min
    module.MELON_TILES_BASE = genome.melon_tiles_base
    module.MELON_TILES_MAX = genome.melon_tiles_max
    module.MAX_EXTRA_LAND = genome.max_extra_land
    module.LAND_OPEN_DAYS = (
        genome.first_land_day, genome.second_land_day, genome.third_land_day,
    )
    module.RESERVE_FRACTION = {
        product: getattr(genome, f"reserve_{product.lower()}")
        for product in PRODUCTS
    }
    if genome.fertilizer_use:
        install_fertilizer_module(module, genome)
    return module.agent


def feature_vector(genome: Ev2Genome) -> list[float]:
    values = genome.phenotype()
    result = []
    for value in values.values():
        result.append(float(value))
    return result

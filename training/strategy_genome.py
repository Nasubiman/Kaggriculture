"""Structured, constraint-preserving strategy genomes for Kaggriculture."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import random
from typing import Any


LAYOUT_FAMILIES = ("rui", "compact", "rows", "checker")
CASH_LAYOUTS = ("near", "far")
OPENING_MODES = ("rui_scripted", "generic")
OPENING_ANIMALS = ("COW", "SHEEP")
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


@dataclass(frozen=True)
class StrategyGenome:
    opening_mode: str = "rui_scripted"
    opening_animal: str = "COW"
    opening_animals: int = 2
    opening_hands: int = 6
    transition_day: int = 10
    cow_count: int = 8
    sheep_count: int = 8
    wheat_tiles: int = 0
    cash_tiles: int = 0
    mature_hands: int = 11
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
    late_wheat_tiles: int = 0
    late_cash_tiles: int = 0
    late_hands: int = 11
    late_service_order: str = "care_fertilizer_harvest"

    def normalized(self) -> "StrategyGenome":
        values = asdict(self)
        values["opening_mode"] = _choice(values["opening_mode"], OPENING_MODES)
        values["opening_animal"] = _choice(values["opening_animal"], OPENING_ANIMALS)
        values["layout_family"] = _choice(values["layout_family"], LAYOUT_FAMILIES)
        values["cash_layout"] = _choice(values["cash_layout"], CASH_LAYOUTS)
        values["service_order"] = _choice(values["service_order"], SERVICE_ORDERS)
        values["late_service_order"] = _choice(
            values["late_service_order"], SERVICE_ORDERS
        )
        values["opening_animals"] = _clip_int(values["opening_animals"], 1, 4)
        values["opening_hands"] = _clip_int(values["opening_hands"], 4, 8)
        values["transition_day"] = _clip_int(values["transition_day"], 8, 12)
        values["cow_count"] = _clip_int(values["cow_count"], 6, 16)
        values["sheep_count"] = _clip_int(values["sheep_count"], 2, 12)
        values["wheat_tiles"] = _clip_int(values["wheat_tiles"], 0, 5)
        values["cash_tiles"] = _clip_int(values["cash_tiles"], 0, 16)
        values["mature_hands"] = _clip_int(values["mature_hands"], 8, 13)
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
        values["late_wheat_tiles"] = _clip_int(values["late_wheat_tiles"], 0, 5)
        values["late_cash_tiles"] = _clip_int(values["late_cash_tiles"], 0, 16)
        values["late_hands"] = _clip_int(values["late_hands"], 6, 13)
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

        # The mature strategy is restricted to the unlocked top half.
        overflow = (
            values["cow_count"]
            + values["sheep_count"]
            + values["wheat_tiles"]
            + values["cash_tiles"]
            - 48
        )
        for name, floor in (("cash_tiles", 0), ("wheat_tiles", 0), ("sheep_count", 2)):
            if overflow <= 0:
                break
            removable = max(0, values[name] - floor)
            removed = min(removable, overflow)
            values[name] -= removed
            overflow -= removed
        late_overflow = (
            values["late_cow_count"]
            + values["late_sheep_count"]
            + values["late_wheat_tiles"]
            + values["late_cash_tiles"]
            - 48
        )
        for name, floor in (
            ("late_cash_tiles", 0),
            ("late_wheat_tiles", 0),
            ("late_sheep_count", 0),
        ):
            if late_overflow <= 0:
                break
            removable = max(0, values[name] - floor)
            removed = min(removable, late_overflow)
            values[name] -= removed
            late_overflow -= removed
        return StrategyGenome(**values)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self.normalized())

    def key(self) -> str:
        values = self.to_dict()
        return "|".join(f"{name}={values[name]}" for name in values)


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
    if phase == "late":
        cow_count = genome.late_cow_count
        sheep_count = genome.late_sheep_count
        wheat_tiles = genome.late_wheat_tiles
        cash_tiles = genome.late_cash_tiles
    else:
        cow_count = genome.cow_count
        sheep_count = genome.sheep_count
        wheat_tiles = genome.wheat_tiles
        cash_tiles = genome.cash_tiles
    half = board_size // 2
    cells = [(x, y) for y in range(half) for x in range(board_size)]
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
    elif genome.layout_family == "rows":
        cow_order, sheep_order = rows, far
    elif genome.layout_family == "checker":
        cow_order, sheep_order = checker, list(reversed(checker))
    else:
        cow_order, sheep_order = compact, far

    if genome.opening_mode == "rui_scripted":
        cow_order = _unique([(4, 4), (4, 3)] + cow_order)

    cows = cow_order[:cow_count]
    occupied = set(cows)
    sheep = [position for position in sheep_order if position not in occupied][
        :sheep_count
    ]
    occupied.update(sheep)
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
    targets = layout_targets(genome, phase="middle")
    late_targets = layout_targets(genome, phase="late")
    module.COW_START_DAY = genome.transition_day
    module.COW_TARGET = genome.cow_count
    module.SHEEP_TARGET = genome.sheep_count
    module.WHEAT_TILES = genome.wheat_tiles
    module.CASH_CROP_TILES = genome.cash_tiles
    module.COW_HANDS = genome.mature_hands
    module.COW_PURCHASE_BATCH = genome.purchase_batch
    module.COW_FIRST_PURCHASE = genome.cow_first
    module.WHEAT_PICKUP_BATCH = genome.wheat_pickup_batch
    module.SALE_PROCEEDS_FACTOR = genome.sale_factor
    module.OPENING_ANIMAL = genome.opening_animal
    module.OPENING_ANIMAL_TARGET = genome.opening_animals
    module.OPENING_REPLANT = genome.replant
    module.USE_LEARNED_MACRO = False
    module.crop_agent.TARGET_HANDS = genome.opening_hands
    phase_state = {"late": False}
    module._cow_targets = lambda _size: (
        late_targets["cows"] if phase_state["late"] else targets["cows"]
    )
    module._sheep_targets = lambda _size: (
        late_targets["sheep"] if phase_state["late"] else targets["sheep"]
    )
    module._wheat_targets = lambda _size: (
        late_targets["wheat"] if phase_state["late"] else targets["wheat"]
    )
    module._cash_crop_targets = lambda _size: (
        late_targets["cash"] if phase_state["late"] else targets["cash"]
    )

    def apply_phase(day: int) -> None:
        late = day >= genome.second_transition_day
        phase_state["late"] = late
        if late:
            module.COW_TARGET = genome.late_cow_count
            module.SHEEP_TARGET = genome.late_sheep_count
            module.WHEAT_TILES = genome.late_wheat_tiles
            module.CASH_CROP_TILES = genome.late_cash_tiles
            module.COW_HANDS = genome.late_hands
            order = genome.late_service_order.split("_")
        else:
            module.COW_TARGET = genome.cow_count
            module.SHEEP_TARGET = genome.sheep_count
            module.WHEAT_TILES = genome.wheat_tiles
            module.CASH_CROP_TILES = genome.cash_tiles
            module.COW_HANDS = genome.mature_hands
            order = genome.service_order.split("_")
        priorities = {name: index + 3 for index, name in enumerate(order)}
        module.CARE_PRIORITY = priorities["care"]
        module.FERTILIZER_PRIORITY = priorities["fertilizer"]
        module.ANIMAL_HARVEST_PRIORITY = priorities["harvest"]

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
        apply_phase(day)
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


FIELD_CHOICES: dict[str, tuple[Any, ...]] = {
    "opening_mode": OPENING_MODES,
    "opening_animal": OPENING_ANIMALS,
    "opening_animals": tuple(range(1, 5)),
    "opening_hands": tuple(range(4, 9)),
    "transition_day": tuple(range(8, 13)),
    "cow_count": tuple(range(6, 17)),
    "sheep_count": tuple(range(2, 13)),
    "wheat_tiles": tuple(range(0, 6)),
    "cash_tiles": tuple(range(0, 17)),
    "mature_hands": tuple(range(8, 14)),
    "purchase_batch": tuple(range(1, 7)),
    "cow_first": (False, True),
    "replant": (False, True),
    "wheat_pickup_batch": tuple(range(4, 21, 2)),
    "sale_factor": tuple(round(value / 100, 2) for value in range(30, 91, 5)),
    "layout_family": LAYOUT_FAMILIES,
    "cash_layout": CASH_LAYOUTS,
    "mirror": (False, True),
    "service_order": SERVICE_ORDERS,
    "second_transition_day": tuple(range(13, 27)),
    "late_cow_count": tuple(range(4, 17)),
    "late_sheep_count": tuple(range(0, 13)),
    "late_wheat_tiles": tuple(range(0, 6)),
    "late_cash_tiles": tuple(range(0, 17)),
    "late_hands": tuple(range(6, 14)),
    "late_service_order": SERVICE_ORDERS,
}


def mutate(
    parent: StrategyGenome, rng: random.Random, changes: int | None = None
) -> StrategyGenome:
    values = parent.normalized().to_dict()
    count = changes or rng.choices((1, 2, 3, 4), weights=(35, 40, 20, 5))[0]
    names = rng.sample(list(FIELD_CHOICES), min(count, len(FIELD_CHOICES)))
    for name in names:
        choices = FIELD_CHOICES[name]
        current = values[name]
        index = min(
            range(len(choices)),
            key=lambda i: abs(float(choices[i]) - float(current))
            if isinstance(current, (int, float)) and not isinstance(current, bool)
            else 0 if choices[i] == current else 1,
        )
        if rng.random() < 0.20 or not isinstance(current, (int, float)):
            values[name] = rng.choice(choices)
        else:
            step = rng.choice((-2, -1, 1, 2))
            values[name] = choices[max(0, min(len(choices) - 1, index + step))]
    return StrategyGenome(**values).normalized()


def crossover(
    first: StrategyGenome, second: StrategyGenome, rng: random.Random
) -> StrategyGenome:
    a, b = first.to_dict(), second.to_dict()
    return StrategyGenome(
        **{name: a[name] if rng.random() < 0.5 else b[name] for name in a}
    ).normalized()


def feature_vector(genome: StrategyGenome) -> list[float]:
    values = genome.normalized().to_dict()
    vector = []
    for name, choices in FIELD_CHOICES.items():
        value = values[name]
        index = choices.index(value)
        vector.append(index / max(1, len(choices) - 1))
    return vector

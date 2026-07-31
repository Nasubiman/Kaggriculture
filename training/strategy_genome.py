"""Structured, constraint-preserving strategy genomes for Kaggriculture."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import random
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


FIELD_CHOICES: dict[str, tuple[Any, ...]] = {
    "strategy_family": STRATEGY_FAMILIES,
    "opening_mode": OPENING_MODES,
    "opening_animal": OPENING_ANIMALS,
    "opening_animals": tuple(range(1, 5)),
    "opening_hands": tuple(range(4, 9)),
    "opening_cows": tuple(range(1, 5)),
    "opening_sheep": tuple(range(0, 5)),
    "transition_day": tuple(range(7, 13)),
    "cow_count": tuple(range(6, 17)),
    "sheep_count": tuple(range(2, 13)),
    "goose_count": tuple(range(0, 7)),
    "wheat_tiles": tuple(range(0, 17)),
    "cash_tiles": tuple(range(0, 41)),
    "mature_hands": tuple(range(8, 14)),
    "hand_ramp_day": tuple(range(0, 13)),
    "hand_ramp_target": tuple(range(4, 13)),
    "hand_full_day": tuple(range(0, 13)),
    "land_target": tuple(range(1, 5)),
    "land_first_day": tuple(range(6, 15)),
    "land_second_day": tuple(range(6, 30)),
    "livestock_policy": LIVESTOCK_POLICIES,
    "adaptive_day": tuple(range(6, 13)),
    "price_gap": tuple(range(0, 41, 5)),
    "cow_heavy_cows": tuple(range(6, 17)),
    "cow_heavy_sheep": tuple(range(0, 7)),
    "sheep_heavy_cows": tuple(range(2, 9)),
    "sheep_heavy_sheep": tuple(range(6, 13)),
    "adaptive_goose_count": tuple(range(0, 5)),
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
    "late_goose_count": tuple(range(0, 7)),
    "late_wheat_tiles": tuple(range(0, 21)),
    "late_cash_tiles": tuple(range(0, 41)),
    "late_hands": tuple(range(6, 14)),
    "late_service_order": SERVICE_ORDERS,
    "third_transition_day": tuple(range(15, 29)),
    "end_cow_count": tuple(range(2, 17)),
    "end_sheep_count": tuple(range(0, 13)),
    "end_goose_count": tuple(range(0, 7)),
    "end_wheat_tiles": tuple(range(0, 21)),
    "end_cash_tiles": tuple(range(0, 31)),
    "end_hands": tuple(range(6, 14)),
    "end_service_order": SERVICE_ORDERS,
}


GENE_BLOCKS: dict[str, tuple[str, ...]] = {
    "opening": (
        "opening_mode", "opening_animal", "opening_animals", "opening_hands",
        "opening_cows", "opening_sheep", "replant", "transition_day",
    ),
    "expansion": (
        "land_target", "land_first_day", "land_second_day", "hand_ramp_day",
        "hand_ramp_target", "hand_full_day", "mature_hands",
    ),
    "livestock": (
        "livestock_policy", "adaptive_day", "price_gap", "cow_count",
        "sheep_count", "goose_count", "cow_heavy_cows", "cow_heavy_sheep",
        "sheep_heavy_cows", "sheep_heavy_sheep", "adaptive_goose_count",
        "purchase_batch", "cow_first",
    ),
    "production": (
        "wheat_tiles", "cash_tiles", "wheat_pickup_batch", "sale_factor",
        "second_transition_day", "late_wheat_tiles", "late_cash_tiles",
    ),
    "endgame": (
        "third_transition_day", "end_cow_count", "end_sheep_count",
        "end_goose_count", "end_wheat_tiles", "end_cash_tiles", "end_hands",
        "end_service_order",
    ),
    "layout_service": (
        "layout_family", "cash_layout", "mirror", "service_order",
        "late_cow_count", "late_sheep_count", "late_goose_count",
        "late_hands", "late_service_order",
    ),
}


def family_seed_genomes(
    base: StrategyGenome | None = None,
) -> tuple[StrategyGenome, ...]:
    """Coherent macro anchors; scalar search is performed inside each family."""
    legacy = replace(
        (base or StrategyGenome()).normalized(), strategy_family="legacy"
    )
    crop = replace(legacy, strategy_family="crop_rotation")
    if base is None:
        crop = replace(
            crop,
            second_transition_day=20,
            late_wheat_tiles=10,
            third_transition_day=27,
            end_wheat_tiles=0,
        )
    expansion = replace(
        legacy,
        strategy_family="land_expansion",
        land_target=3,
        land_first_day=7,
        land_second_day=10,
        hand_ramp_day=7,
        hand_ramp_target=9,
        hand_full_day=9,
        mature_hands=12,
        layout_family="rank1",
    )
    market = replace(
        legacy,
        strategy_family="market_livestock",
        livestock_policy="market",
        adaptive_day=7,
        layout_family="rank1",
    )
    hybrid = replace(legacy, strategy_family="hybrid")
    return tuple(
        genome.normalized()
        for genome in (
            legacy,
            crop,
            expansion,
            market,
            hybrid,
            rank1_seed_genome(),
        )
    )


def active_field_names(genome: StrategyGenome) -> set[str]:
    """Return genes that can change behavior for this conditional genome."""
    genome = genome.normalized()
    active = {
        "strategy_family", "opening_mode", "opening_hands", "transition_day",
        "cow_count", "sheep_count", "wheat_tiles", "cash_tiles",
        "mature_hands", "purchase_batch", "cow_first", "wheat_pickup_batch",
        "sale_factor", "layout_family", "cash_layout", "service_order",
        "second_transition_day", "late_cow_count", "late_sheep_count",
        "late_wheat_tiles", "late_cash_tiles", "late_hands",
        "late_service_order",
    }
    if genome.opening_mode == "generic":
        active.update(("opening_animal", "opening_animals", "replant", "mirror"))
    elif genome.opening_mode == "mixed":
        active.update(("opening_cows", "opening_sheep", "replant", "mirror"))
    if genome.strategy_family in ("land_expansion", "hybrid"):
        active.update(
            (
                "land_target", "land_first_day", "hand_ramp_day",
                "hand_ramp_target", "hand_full_day",
            )
        )
        if genome.land_target >= 3:
            active.add("land_second_day")
    if genome.strategy_family in ("market_livestock", "hybrid"):
        active.update(("livestock_policy", "goose_count", "late_goose_count"))
        if genome.livestock_policy == "market":
            active.update(
                (
                    "adaptive_day", "price_gap", "cow_heavy_cows",
                    "cow_heavy_sheep", "sheep_heavy_cows",
                    "sheep_heavy_sheep", "adaptive_goose_count",
                )
            )
    if genome.strategy_family in ("crop_rotation", "hybrid"):
        active.update(
            (
                "third_transition_day", "end_cow_count", "end_sheep_count",
                "end_wheat_tiles", "end_cash_tiles", "end_hands",
                "end_service_order",
            )
        )
        if genome.strategy_family == "hybrid":
            active.add("end_goose_count")
    return active


def mutate(
    parent: StrategyGenome, rng: random.Random, changes: int | None = None
) -> StrategyGenome:
    values = parent.normalized().to_dict()
    if rng.random() < 0.10:
        alternatives = [
            genome
            for genome in family_seed_genomes(parent)
            if genome.strategy_family != parent.strategy_family
        ]
        if alternatives:
            values = rng.choice(alternatives).to_dict()
            parent = StrategyGenome(**values)

    active = active_field_names(parent)
    count = changes or rng.choices((1, 2, 3, 4), weights=(25, 40, 25, 10))[0]
    if rng.random() < 0.55:
        blocks = [
            tuple(name for name in names if name in active)
            for names in GENE_BLOCKS.values()
        ]
        blocks = [block for block in blocks if block]
        block = rng.choice(blocks)
        block_count = min(len(block), max(2, count))
        names = rng.sample(list(block), block_count)
    else:
        choices = sorted(active)
        names = rng.sample(choices, min(count, len(choices)))
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
    family_parent = a if rng.random() < 0.5 else b
    values = dict(family_parent)
    covered = {"strategy_family"}
    for names in GENE_BLOCKS.values():
        source = a if rng.random() < 0.5 else b
        for name in names:
            values[name] = source[name]
            covered.add(name)
    for name in values.keys() - covered:
        values[name] = a[name] if rng.random() < 0.5 else b[name]
    return StrategyGenome(**values).normalized()


def feature_vector(genome: StrategyGenome) -> list[float]:
    values = genome.normalized().to_dict()
    active = active_field_names(genome)
    defaults = StrategyGenome().to_dict()
    vector: list[float] = []
    for name, choices in FIELD_CHOICES.items():
        enabled = name in active
        value = values[name] if enabled else defaults[name]
        index = choices.index(value)
        vector.append(index / max(1, len(choices) - 1))
        vector.append(float(enabled))
    return vector

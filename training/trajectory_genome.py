"""Spatial and action-order trajectory genomes for Kaggriculture.

The genome deliberately sits above the current reactive policy.  It changes
where that policy builds, the order in which it fills the board, and which
class of work leads each part of the season.  Legality, crisis recovery,
inventory handling, and market logic remain with the incumbent agent.
"""

from __future__ import annotations

# --- BEGIN TRAJECTORY RUNTIME ---
from dataclasses import asdict, dataclass, replace
import json
import random
from typing import Any


PHASE_COUNT = 5
PHASE_DAY_FIELDS = tuple(f"phase_{index}_day" for index in range(1, PHASE_COUNT))
BLOCK_FIELDS = tuple(f"block_{index}" for index in range(PHASE_COUNT))
SWEEP_FIELDS = tuple(f"sweep_{index}" for index in range(PHASE_COUNT))
TRAVEL_FIELDS = tuple(f"travel_{index}" for index in range(PHASE_COUNT))

LAYOUT_MODES = (
    "baseline",
    "ev6_band",
    "shed_ring",
    "horizontal_band",
    "vertical_spokes",
)
CROP_PATH_MODES = ("baseline", "outer_first", "row_snake", "column_snake")
BLOCK_MODES = (
    "baseline",
    "establish",
    "livestock",
    "crop",
    "ev6_service",
    "realize",
    "cleanup",
)
SWEEP_MODES = (
    "baseline",
    "row_lr",
    "row_snake",
    "column_snake",
    "center_out",
    "band_out",
)


@dataclass(frozen=True)
class TrajectoryGenome:
    """A five-segment spatial work program compiled onto the incumbent."""

    phase_1_day: int = 5
    phase_2_day: int = 10
    phase_3_day: int = 17
    phase_4_day: int = 23

    layout_mode: str = "baseline"
    crop_path_mode: str = "baseline"
    mirror_x: int = 0
    mirror_y: int = 0

    block_0: str = "baseline"
    block_1: str = "baseline"
    block_2: str = "baseline"
    block_3: str = "baseline"
    block_4: str = "baseline"

    sweep_0: str = "baseline"
    sweep_1: str = "baseline"
    sweep_2: str = "baseline"
    sweep_3: str = "baseline"
    sweep_4: str = "baseline"

    travel_0: int = 9
    travel_1: int = 9
    travel_2: int = 9
    travel_3: int = 9
    travel_4: int = 9
    sweep_strength: int = 2

    def normalized(self) -> "TrajectoryGenome":
        values = asdict(self)
        previous = 0
        for index, name in enumerate(PHASE_DAY_FIELDS, start=1):
            low = previous + 1
            high = 29 - (PHASE_COUNT - 1 - index)
            values[name] = _clip_int(values[name], low, high)
            previous = values[name]
        values["layout_mode"] = _choice(values["layout_mode"], LAYOUT_MODES)
        values["crop_path_mode"] = _choice(
            values["crop_path_mode"], CROP_PATH_MODES
        )
        values["mirror_x"] = int(bool(values["mirror_x"]))
        values["mirror_y"] = int(bool(values["mirror_y"]))
        for name in BLOCK_FIELDS:
            values[name] = _choice(values[name], BLOCK_MODES)
        for name in SWEEP_FIELDS:
            values[name] = _choice(values[name], SWEEP_MODES)
        for name in TRAVEL_FIELDS:
            values[name] = _clip_int(values[name], 3, 18)
        values["sweep_strength"] = _clip_int(values["sweep_strength"], 0, 4)
        return TrajectoryGenome(**values)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self.normalized())

    def key(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    def phase_days(self) -> tuple[int, ...]:
        genome = self.normalized()
        return (0, *(getattr(genome, name) for name in PHASE_DAY_FIELDS))


def _clip_int(value: Any, low: int, high: int) -> int:
    return max(low, min(high, int(round(float(value)))))


def _choice(value: Any, choices: tuple[str, ...]) -> str:
    return str(value) if str(value) in choices else choices[0]


def phase_index(genome: TrajectoryGenome, day: int) -> int:
    result = 0
    for index, start in enumerate(genome.phase_days()):
        if day >= start:
            result = index
        else:
            break
    return result


def _mirrored(position: tuple[int, int], size: int, genome: TrajectoryGenome):
    x, y = position
    if genome.mirror_x:
        x = size - 1 - x
    if genome.mirror_y:
        y = size - 1 - y
    return x, y


def _layout_score(
    position: tuple[int, int],
    size: int,
    mode: str,
    genome: TrajectoryGenome,
) -> tuple[Any, ...]:
    x, y = _mirrored(position, size, genome)
    half = size // 2
    center_x = half - 0.5
    center_y = half - 0.5
    dx = abs(x - center_x)
    dy = abs(y - center_y)
    if mode == "ev6_band":
        # Public episode 89256171 builds a horizontal livestock belt through
        # rows 2--5, with the densest part immediately around the sheds.
        return (2.4 * dy + 0.65 * dx, dy, y, x)
    if mode == "horizontal_band":
        return (3.2 * dy + 0.25 * dx, y, x)
    if mode == "vertical_spokes":
        return (2.8 * dx + 0.45 * dy, x, y)
    # A ring delays the four shed cells themselves and surrounds them first.
    ring = max(dx, dy)
    center_penalty = 2 if dx < 1 and dy < 1 else 0
    return (center_penalty, ring, dx + dy, y, x)


def _crop_score(
    position: tuple[int, int],
    size: int,
    mode: str,
    genome: TrajectoryGenome,
) -> tuple[Any, ...]:
    x, y = _mirrored(position, size, genome)
    center = (size - 1) / 2.0
    if mode == "outer_first":
        return (-(abs(x - center) + abs(y - center)), y, x)
    if mode == "row_snake":
        return (y, x if y % 2 == 0 else size - 1 - x)
    if mode == "column_snake":
        return (x, y if x % 2 == 0 else size - 1 - y)
    return (0, y, x)


def _sweep_rank(
    position: tuple[int, int], size: int, mode: str
) -> float:
    x, y = position
    center = (size - 1) / 2.0
    if mode == "row_lr":
        order = y * size + x
    elif mode == "row_snake":
        order = y * size + (x if y % 2 == 0 else size - 1 - x)
    elif mode == "column_snake":
        order = x * size + (y if x % 2 == 0 else size - 1 - y)
    elif mode == "center_out":
        order = (abs(x - center) + abs(y - center)) * size + y
    elif mode == "band_out":
        order = abs(y - center) * size + abs(x - center)
    else:
        return 0.0
    # Earlier locations get a larger bonus.  The result is deliberately
    # bounded so that it only orders jobs inside a safety priority tier.
    return float(size * size - order)


def _reason_group(reason: str) -> str:
    if reason in {"critical_feed", "critical_water"}:
        return "critical"
    if reason.startswith("build_") or reason in {
        "clear_animal_slot", "replace_incompatible_structure"
    }:
        return "build"
    if reason.startswith("place_"):
        return "place"
    if reason.startswith("plant_"):
        return "plant"
    if reason == "feed":
        return "feed"
    if reason in {"animal_harvest", "fertilizer"}:
        return "animal_yield"
    if reason == "care":
        return "care"
    if reason in {"ongoing_water", "yield_water", "final_growth_water"}:
        return "crop_water"
    if reason in {"ongoing_harvest", "ripe_harvest"}:
        return "crop_harvest"
    if reason == "profitable_fertilizer":
        return "fertilize"
    if reason == "dig_weed":
        return "cleanup"
    if reason.startswith("terminal_"):
        return "terminal"
    return "other"


# Absolute service tiers.  Critical survival jobs never pass through these
# tables.  A block is a reusable partial trajectory that can be swapped into a
# different season segment without changing the remainder of the policy.
BLOCK_PRIORITIES: dict[str, dict[str, int]] = {
    "baseline": {},
    "establish": {"place": 1, "build": 2, "plant": 3, "cleanup": 3},
    "livestock": {
        "feed": 1, "place": 1, "animal_yield": 2, "care": 2,
        "build": 2, "crop_harvest": 3,
    },
    "crop": {
        "crop_harvest": 1, "crop_water": 2, "fertilize": 2,
        "plant": 3, "care": 4,
    },
    "ev6_service": {
        "feed": 1, "place": 1, "animal_yield": 2, "crop_harvest": 2,
        "fertilize": 2, "care": 3, "crop_water": 3, "build": 3,
        "plant": 4,
    },
    "realize": {
        "terminal": 0, "crop_harvest": 1, "animal_yield": 1,
        "crop_water": 3, "care": 4, "plant": 5, "build": 5,
    },
    "cleanup": {
        "terminal": 0, "crop_harvest": 1, "animal_yield": 1,
        "cleanup": 2, "crop_water": 3, "care": 5, "plant": 5,
        "build": 5,
    },
}


def configure_module(module: Any, genome: TrajectoryGenome):
    """Install a spatial/action trajectory on a freshly loaded policy module."""
    if hasattr(module, "_TRAJECTORY_AGENT_BEFORE"):
        module.agent = module._TRAJECTORY_AGENT_BEFORE
        module._reserved_animal_slots = module._TRAJECTORY_SLOTS_BEFORE
        module._field_jobs = module._TRAJECTORY_JOBS_BEFORE
        module.TRAVEL_COST = module._TRAJECTORY_BASE_TRAVEL

    genome = genome.normalized()
    base_agent = module.agent
    base_slots = module._reserved_animal_slots
    base_jobs = module._field_jobs
    base_travel = float(getattr(module, "TRAVEL_COST", 9.0))
    module._TRAJECTORY_AGENT_BEFORE = base_agent
    module._TRAJECTORY_SLOTS_BEFORE = base_slots
    module._TRAJECTORY_JOBS_BEFORE = base_jobs
    module._FROZEN_TRAJECTORY = genome.to_dict()

    def trajectory_slots(farm):
        if genome.layout_mode == "baseline" and genome.crop_path_mode == "baseline":
            return base_slots(farm)
        tiles = farm.get("tiles", []) or []
        size = len(tiles)
        unlocked = set(farm.get("unlocked_quadrants", []) or ["NW"])
        slots = []
        by_quadrant = {}
        for quadrant in ("NW", "NE", "SW", "SE"):
            if quadrant not in unlocked:
                continue
            cells = [
                (x, y)
                for y, row in enumerate(tiles)
                for x, tile in enumerate(row)
                if tile != "LOCKED"
                and module._quadrant_of((x, y), size) == quadrant
            ]
            if genome.layout_mode == "baseline":
                baseline_slots, baseline_zones = base_slots(farm)
                chosen = list((baseline_zones.get(quadrant) or {}).get("reserved", []))
            else:
                cells.sort(
                    key=lambda position: _layout_score(
                        position, size, genome.layout_mode, genome
                    )
                )
                quota = int((getattr(module, "ANIMAL_SLOTS", {}) or {}).get(
                    quadrant, 0
                ))
                chosen = cells[: max(0, min(quota, len(cells)))]
            remaining = [position for position in cells if position not in set(chosen)]
            if genome.crop_path_mode == "baseline":
                if genome.layout_mode == "baseline":
                    remaining = list(
                        (baseline_zones.get(quadrant) or {}).get("crops", remaining)
                    )
                else:
                    remaining.sort(
                        key=lambda position: _layout_score(
                            position, size, genome.layout_mode, genome
                        )
                    )
            else:
                remaining.sort(
                    key=lambda position: _crop_score(
                        position, size, genome.crop_path_mode, genome
                    )
                )
            by_quadrant[quadrant] = {
                "reserved": chosen,
                "crops": remaining,
            }
            slots.extend(chosen)
        return slots, by_quadrant

    def trajectory_jobs(obs, farm, private, roles, liquidation):
        jobs = base_jobs(obs, farm, private, roles, liquidation)
        day = int(obs.get("day", 0) or 0)
        index = phase_index(genome, day)
        block = getattr(genome, BLOCK_FIELDS[index])
        sweep = getattr(genome, SWEEP_FIELDS[index])
        priorities = BLOCK_PRIORITIES[block]
        size = len(farm.get("tiles", []) or [])
        strength = (0.0, 0.8, 1.8, 3.2, 5.0)[genome.sweep_strength]
        result = []
        for raw_job in jobs:
            job = dict(raw_job)
            group = _reason_group(str(job.get("reason", "")))
            # Survival is an invariant of the search space.
            if group != "critical" and group in priorities:
                job["priority"] = priorities[group]
            target = job.get("target")
            if sweep != "baseline" and target is not None and size:
                job["value"] = float(job.get("value", 0.0)) + strength * _sweep_rank(
                    tuple(target), size, sweep
                )
            result.append(job)
        return result

    def trajectory_agent(obs, config=None):
        index = phase_index(genome, int(obs.get("day", 0) or 0))
        module.TRAVEL_COST = float(getattr(genome, TRAVEL_FIELDS[index]))
        return base_agent(obs, config)

    module._reserved_animal_slots = trajectory_slots
    module._field_jobs = trajectory_jobs
    module.agent = trajectory_agent
    module._TRAJECTORY_BASE_TRAVEL = base_travel
    return trajectory_agent


# --- END TRAJECTORY RUNTIME ---


def current_trajectory() -> TrajectoryGenome:
    """Identity wrapper: behaviorally identical to the incumbent."""
    return TrajectoryGenome()


def ev6_trajectory() -> TrajectoryGenome:
    """A state-repaired approximation of public episode 89256171."""
    return TrajectoryGenome(
        layout_mode="ev6_band",
        crop_path_mode="outer_first",
        block_0="establish",
        block_1="livestock",
        block_2="ev6_service",
        block_3="ev6_service",
        block_4="realize",
        sweep_0="row_snake",
        sweep_1="band_out",
        sweep_2="band_out",
        sweep_3="row_snake",
        sweep_4="center_out",
        travel_0=7,
        travel_1=7,
        travel_2=8,
        travel_3=9,
        travel_4=11,
        sweep_strength=2,
    ).normalized()


def anchor_trajectories() -> list[TrajectoryGenome]:
    base = current_trajectory()
    trace = ev6_trajectory()
    anchors = [base, trace]
    blocks = {
        "layout": ("layout_mode", "crop_path_mode"),
        "service": BLOCK_FIELDS,
        "sweep": (*SWEEP_FIELDS, "sweep_strength"),
        "travel": TRAVEL_FIELDS,
    }
    for fields in blocks.values():
        anchors.append(
            replace(base, **{name: getattr(trace, name) for name in fields}).normalized()
        )
    # Segment-level donors make trajectory splicing explicit in stage zero.
    for start, end in ((0, 2), (1, 4), (2, 5)):
        values = {}
        for index in range(start, end):
            values[BLOCK_FIELDS[index]] = getattr(trace, BLOCK_FIELDS[index])
            values[SWEEP_FIELDS[index]] = getattr(trace, SWEEP_FIELDS[index])
            values[TRAVEL_FIELDS[index]] = getattr(trace, TRAVEL_FIELDS[index])
        anchors.append(replace(base, **values).normalized())
    return list({genome.key(): genome for genome in anchors}.values())


def mutate(
    genome: TrajectoryGenome,
    rng: random.Random,
    changes: int = 1,
) -> TrajectoryGenome:
    result = genome.normalized()
    groups = ("phase", "layout", "segment", "block", "sweep", "travel")
    for _ in range(max(1, changes)):
        group = rng.choice(groups)
        values: dict[str, Any] = {}
        if group == "phase":
            name = rng.choice(PHASE_DAY_FIELDS)
            values[name] = getattr(result, name) + rng.choice((-1, 1))
        elif group == "layout":
            name = rng.choice(
                ("layout_mode", "crop_path_mode", "mirror_x", "mirror_y")
            )
            if name == "layout_mode":
                values[name] = rng.choice(LAYOUT_MODES)
            elif name == "crop_path_mode":
                values[name] = rng.choice(CROP_PATH_MODES)
            else:
                values[name] = 1 - int(getattr(result, name))
        elif group == "segment":
            index = rng.randrange(PHASE_COUNT)
            donor = rng.choice(anchor_trajectories())
            values[BLOCK_FIELDS[index]] = getattr(donor, BLOCK_FIELDS[index])
            values[SWEEP_FIELDS[index]] = getattr(donor, SWEEP_FIELDS[index])
            values[TRAVEL_FIELDS[index]] = getattr(donor, TRAVEL_FIELDS[index])
        elif group == "block":
            name = rng.choice(BLOCK_FIELDS)
            values[name] = rng.choice(BLOCK_MODES)
        elif group == "sweep":
            if rng.random() < 0.8:
                name = rng.choice(SWEEP_FIELDS)
                values[name] = rng.choice(SWEEP_MODES)
            else:
                name = "sweep_strength"
                values[name] = getattr(result, name) + rng.choice((-1, 1))
        else:
            name = rng.choice(TRAVEL_FIELDS)
            values[name] = getattr(result, name) + rng.choice((-2, -1, 1, 2))
        result = replace(result, **values).normalized()
    return result

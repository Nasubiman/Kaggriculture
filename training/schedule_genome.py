"""Daily milestone schedules compiled onto the current reactive policy."""

from __future__ import annotations

# --- BEGIN SCHEDULE RUNTIME ---
from dataclasses import asdict, dataclass, replace
import json
import random
from typing import Any


PHASE_COUNT = 8
PHASE_DAY_FIELDS = tuple(f"day_{index}" for index in range(1, PHASE_COUNT))
HERD_FIELDS = tuple(f"herd_{index}" for index in range(PHASE_COUNT))
HAND_FIELDS = tuple(f"hands_{index}" for index in range(PHASE_COUNT))


@dataclass(frozen=True)
class ScheduleGenome:
    """A compact 30-day program of economic milestones.

    The low-level policy remains reactive.  This genome controls the intended
    herd and labour level at eight milestones, the permanent spatial budget,
    land timing, purchasing horizon, and the start/strength of realization.
    """

    day_1: int = 5
    day_2: int = 7
    day_3: int = 9
    day_4: int = 11
    day_5: int = 17
    day_6: int = 22
    day_7: int = 29

    herd_0: int = 5
    herd_1: int = 9
    herd_2: int = 9
    herd_3: int = 9
    herd_4: int = 13
    herd_5: int = 13
    herd_6: int = 13
    herd_7: int = 13

    hands_0: int = 12
    hands_1: int = 12
    hands_2: int = 12
    hands_3: int = 12
    hands_4: int = 12
    hands_5: int = 12
    hands_6: int = 12
    hands_7: int = 12

    animal_slots_nw: int = 5
    animal_slots_ne: int = 5
    animal_slots_sw: int = 3
    animal_slots_se: int = 0

    max_extra_land: int = 2
    first_land_day: int = 5
    second_land_day: int = 10
    third_land_day: int = 14
    animal_purchase_last_day: int = 18
    liquidation_turns: int = 22

    realize_day: int = 30
    harvest_priority: int = 2

    def normalized(self) -> "ScheduleGenome":
        values = asdict(self)
        previous = 0
        for index, name in enumerate(PHASE_DAY_FIELDS, start=1):
            low = previous + 1
            high = 29 - (PHASE_COUNT - 1 - index)
            values[name] = _clip_int(values[name], low, high)
            previous = values[name]

        slot_total = 0
        for quadrant in ("nw", "ne", "sw", "se"):
            name = f"animal_slots_{quadrant}"
            values[name] = _clip_int(values[name], 0, 8)
            slot_total += values[name]
        slot_total = max(1, slot_total)

        previous_herd = 0
        for name in HERD_FIELDS:
            values[name] = _clip_int(values[name], previous_herd, slot_total)
            previous_herd = values[name]
        for name in HAND_FIELDS:
            values[name] = _clip_int(values[name], 4, 16)

        values["max_extra_land"] = _clip_int(values["max_extra_land"], 0, 3)
        values["first_land_day"] = _clip_int(values["first_land_day"], 2, 14)
        values["second_land_day"] = _clip_int(
            values["second_land_day"], values["first_land_day"] + 1, 20
        )
        values["third_land_day"] = _clip_int(
            values["third_land_day"], values["second_land_day"] + 1, 24
        )
        values["animal_purchase_last_day"] = _clip_int(
            values["animal_purchase_last_day"], 10, 23
        )
        values["liquidation_turns"] = _clip_int(
            values["liquidation_turns"], 18, 96
        )
        values["realize_day"] = _clip_int(values["realize_day"], 18, 30)
        values["harvest_priority"] = _clip_int(
            values["harvest_priority"], 0, 3
        )
        return ScheduleGenome(**values)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self.normalized())

    def key(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    def phase_days(self) -> tuple[int, ...]:
        genome = self.normalized()
        return (0, *(getattr(genome, name) for name in PHASE_DAY_FIELDS))

    def herd_targets(self) -> tuple[int, ...]:
        genome = self.normalized()
        return tuple(getattr(genome, name) for name in HERD_FIELDS)

    def hand_caps(self) -> tuple[int, ...]:
        genome = self.normalized()
        return tuple(getattr(genome, name) for name in HAND_FIELDS)


def _clip_int(value: Any, low: int, high: int) -> int:
    return max(low, min(high, int(round(float(value)))))


def phase_index(genome: ScheduleGenome, day: int) -> int:
    result = 0
    for index, start in enumerate(genome.phase_days()):
        if day >= start:
            result = index
        else:
            break
    return result


def configure_module(module: Any, genome: ScheduleGenome):
    """Install a schedule on a freshly imported current-policy module."""
    if hasattr(module, "_SCHEDULE_AGENT_BEFORE"):
        module.agent = module._SCHEDULE_AGENT_BEFORE
        module._herd_targets = module._SCHEDULE_HERD_BEFORE
        module._field_jobs = module._SCHEDULE_JOBS_BEFORE

    genome = genome.normalized()
    base_agent = module.agent
    base_herd_targets = module._herd_targets
    base_field_jobs = module._field_jobs
    module._SCHEDULE_AGENT_BEFORE = base_agent
    module._SCHEDULE_HERD_BEFORE = base_herd_targets
    module._SCHEDULE_JOBS_BEFORE = base_field_jobs
    module._FROZEN_SCHEDULE = genome.to_dict()

    module.ANIMAL_SLOTS = {
        "NW": genome.animal_slots_nw,
        "NE": genome.animal_slots_ne,
        "SW": genome.animal_slots_sw,
        "SE": genome.animal_slots_se,
    }
    module.MAX_EXTRA_LAND = genome.max_extra_land
    module.LAND_OPEN_DAYS = (
        genome.first_land_day,
        genome.second_land_day,
        genome.third_land_day,
    )
    module.ANIMAL_PURCHASE_LAST_DAY = genome.animal_purchase_last_day
    module.LIQUIDATION_TURNS = genome.liquidation_turns

    def scheduled_herd_targets(obs, farm, private, capacity):
        day = int(obs.get("day", 0) or 0)
        left = int(getattr(module, "TOTAL_DAYS", 30)) - day
        placed = module._farm_animal_counts(farm)
        owned = {
            animal: placed[animal] + module._private_item_total(private, animal)
            for animal in ("COW", "SHEEP")
        }
        target = genome.herd_targets()[phase_index(genome, day)]
        if day > genome.animal_purchase_last_day or left < 8:
            target = sum(owned.values())
        target_total = min(capacity, max(sum(owned.values()), target))
        core = min(4, target_total)
        targets = {
            "COW": max(3 if core >= 4 else core, owned["COW"]),
            "SHEEP": max(1 if core >= 4 else 0, owned["SHEEP"]),
        }
        opponents = module._opponent_animal_counts(obs)
        while sum(targets.values()) < target_total:
            animal = max(
                ("COW", "SHEEP"),
                key=lambda name: (
                    module._livestock_score(
                        obs, name, targets[name], opponents[name]
                    ),
                    -targets[name],
                    name == "COW",
                ),
            )
            targets[animal] += 1
        return targets

    def scheduled_field_jobs(obs, farm, private, roles, liquidation):
        jobs = base_field_jobs(obs, farm, private, roles, liquidation)
        day = int(obs.get("day", 0) or 0)
        if day < genome.realize_day:
            return jobs
        harvest_reasons = {
            "ripe_harvest",
            "animal_harvest",
            "terminal_crop",
            "terminal_animal",
            "terminal_fertilizer",
        }
        result = []
        for job in jobs:
            if job.get("reason") in harvest_reasons:
                job = dict(job)
                job["priority"] = min(
                    int(job.get("priority", 9)), genome.harvest_priority
                )
            result.append(job)
        return result

    def scheduled_agent(obs, config=None):
        day = int(obs.get("day", 0) or 0)
        module.MAX_HANDS = genome.hand_caps()[phase_index(genome, day)]
        return base_agent(obs, config)

    module._herd_targets = scheduled_herd_targets
    module._field_jobs = scheduled_field_jobs
    module.agent = scheduled_agent
    return scheduled_agent


# --- END SCHEDULE RUNTIME ---


def current_schedule() -> ScheduleGenome:
    """Schedule that is behaviorally identical to the current frozen genome."""
    return ScheduleGenome()


def ev6_schedule() -> ScheduleGenome:
    """High-level milestones extracted from public episode 89256171."""
    return ScheduleGenome(
        herd_0=4,
        herd_1=4,
        herd_2=6,
        herd_3=9,
        herd_4=13,
        herd_5=16,
        herd_6=16,
        herd_7=16,
        hands_0=4,
        hands_1=6,
        hands_2=6,
        hands_3=7,
        hands_4=11,
        hands_5=11,
        hands_6=11,
        hands_7=10,
        animal_slots_ne=6,
        animal_slots_sw=5,
        first_land_day=9,
        second_land_day=12,
        animal_purchase_last_day=17,
        realize_day=22,
        harvest_priority=1,
    ).normalized()


def anchor_schedules() -> list[ScheduleGenome]:
    base = current_schedule()
    trace = ev6_schedule()
    anchors = [base, trace]
    blocks = {
        "herd": (*HERD_FIELDS, "animal_slots_ne", "animal_slots_sw"),
        "labor": HAND_FIELDS,
        "land": ("first_land_day", "second_land_day"),
        "realize": ("realize_day", "harvest_priority"),
    }
    for fields in blocks.values():
        anchors.append(
            replace(
                base,
                **{name: getattr(trace, name) for name in fields},
            ).normalized()
        )
    for first, second in (("herd", "labor"), ("herd", "realize"), ("labor", "realize")):
        fields = (*blocks[first], *blocks[second])
        anchors.append(
            replace(
                base,
                **{name: getattr(trace, name) for name in fields},
            ).normalized()
        )
    return list({genome.key(): genome for genome in anchors}.values())


def mutate(
    genome: ScheduleGenome,
    rng: random.Random,
    changes: int = 1,
) -> ScheduleGenome:
    result = genome.normalized()
    groups = ("days", "herd", "hands", "layout", "land", "realize")
    for _ in range(max(1, changes)):
        group = rng.choice(groups)
        values: dict[str, Any] = {}
        if group == "days":
            name = rng.choice(PHASE_DAY_FIELDS)
            values[name] = getattr(result, name) + rng.choice((-1, 1))
        elif group == "herd":
            start = rng.randrange(PHASE_COUNT)
            delta = rng.choice((-1, 1))
            for name in HERD_FIELDS[start:]:
                values[name] = getattr(result, name) + delta
        elif group == "hands":
            start = rng.randrange(PHASE_COUNT)
            end = rng.randrange(start + 1, PHASE_COUNT + 1)
            delta = rng.choice((-1, 1))
            for name in HAND_FIELDS[start:end]:
                values[name] = getattr(result, name) + delta
        elif group == "layout":
            name = rng.choice(
                ("animal_slots_nw", "animal_slots_ne", "animal_slots_sw")
            )
            values[name] = getattr(result, name) + rng.choice((-1, 1))
        elif group == "land":
            name = rng.choice(
                ("first_land_day", "second_land_day", "max_extra_land")
            )
            values[name] = getattr(result, name) + rng.choice((-1, 1))
        else:
            name = rng.choice(
                ("realize_day", "harvest_priority", "liquidation_turns",
                 "animal_purchase_last_day")
            )
            step = 4 if name == "liquidation_turns" else 1
            values[name] = getattr(result, name) + rng.choice((-step, step))
        result = replace(result, **values).normalized()
    return result


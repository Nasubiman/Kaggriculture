#!/usr/bin/env python3
"""Infer local task-priority rules from aligned rank-1 state/action examples."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import json
from pathlib import Path


MOVES = {"NORTH", "SOUTH", "EAST", "WEST"}
FIRST_YIELD = {"WHEAT": 2, "CARROT": 2, "TOMATO": 8, "STRAWBERRY": 10, "MELON": 10}


def phase(day: int) -> str:
    if day <= 5: return "d00-05"
    if day <= 9: return "d06-09"
    if day <= 17: return "d10-17"
    if day <= 27: return "d18-27"
    return "d28-29"


def available_tasks(tile: object, inventory: dict, day: int) -> tuple[str, ...]:
    if not isinstance(tile, dict):
        return ()
    tasks: list[str] = []
    animal = tile.get("animal")
    if animal:
        if int(tile.get("yield_units", 0)) > 0: tasks.append("HARVEST")
        if bool(tile.get("fertilizer_available")): tasks.append("COLLECT_FERTILIZER")
        if not bool(tile.get("fed_today")) and int(inventory.get("WHEAT", 0)) > 0: tasks.append("FEED")
        if not bool(tile.get("cared_today")): tasks.append("CARE")
        return tuple(tasks)
    if tile.get("kind") == "PLANT":
        crop = str(tile.get("crop", "")); age = day - int(tile.get("planted_day", day))
        if int(tile.get("yield_units", 0)) > 0 and age >= FIRST_YIELD.get(crop, 0):
            tasks.append("HARVEST")
        if not bool(tile.get("watered_today")): tasks.append("WATER")
        if int(inventory.get("FERTILIZER", 0)) > 0 and int(tile.get("fertilized_until_day", -1)) < day:
            tasks.append("FERTILIZE")
    return tuple(tasks)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--json-output", type=Path, required=True)
    args = parser.parse_args()

    choices: dict[str, Counter[str]] = defaultdict(Counter)
    phase_choices: dict[str, dict[str, Counter[str]]] = defaultdict(lambda: defaultdict(Counter))
    hour_actions: dict[str, Counter[int]] = defaultdict(Counter)
    actor_actions: dict[str, Counter[int]] = defaultdict(Counter)
    tile_actions: dict[str, Counter[str]] = defaultdict(Counter)
    actionable = acted = deferred = 0
    rows = 0

    with gzip.open(args.dataset, "rt", encoding="utf-8") as source:
        for line in source:
            row = json.loads(line)
            if row.get("type") != "example": continue
            rows += 1
            obs = row["observation"]; seat = int(row["seat"]); day = int(obs.get("day", 0)); hour = int(obs.get("hour", 0))
            farm = obs["farms"][seat]; private = obs.get("private", {}) or {}
            positions = [farm.get("farmer", [4, 4]), *(farm.get("hands", []) or [])]
            inventories = private.get("inventories", []) or []
            action = row.get("action") or {}; commands = [action.get("farmer") or ["PASS"], *(action.get("hands") or [])]
            for actor, position in enumerate(positions):
                command = commands[actor] if actor < len(commands) else ["PASS"]
                op = str(command[0]) if command else "PASS"
                inventory = inventories[actor] if actor < len(inventories) else {}
                x, y = map(int, position); tile = farm["tiles"][y][x]
                tasks = available_tasks(tile, inventory, day)
                if isinstance(tile, dict) and tile.get("animal"):
                    tile_class = "animal:" + str(tile.get("animal"))
                elif isinstance(tile, dict) and tile.get("kind") == "PLANT":
                    tile_class = "plant:" + str(tile.get("crop"))
                elif isinstance(tile, dict): tile_class = str(tile.get("kind", "dict")).lower()
                elif tile is None: tile_class = "empty"
                else: tile_class = str(tile).lower()
                tile_actions[tile_class][op] += 1
                hour_actions[op][hour] += 1; actor_actions[op][actor] += 1
                if tasks:
                    actionable += 1
                    key = "+".join(tasks)
                    choices[key][op] += 1; phase_choices[phase(day)][key][op] += 1
                    if op in tasks: acted += 1
                    elif op in MOVES or op == "PASS": deferred += 1
            if rows % 25000 == 0: print(f"processed {rows}", flush=True)

    result = {
        "rows": rows, "actionable_actor_turns": actionable,
        "acted_on_local_task": acted, "deferred_with_move_or_pass": deferred,
        "task_choices": {key: dict(value) for key, value in choices.items()},
        "phase_task_choices": {p: {key: dict(value) for key, value in table.items()} for p, table in phase_choices.items()},
        "hour_actions": {key: dict(value) for key, value in hour_actions.items()},
        "actor_actions": {key: dict(value) for key, value in actor_actions.items()},
        "tile_actions": {key: dict(value) for key, value in tile_actions.items()},
    }
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(result, indent=2) + "\n")

    lines = [
        "# Rank-1 inferred reactive rules", "",
        f"- Aligned state/action rows: {rows}",
        f"- Actor-turns with at least one local task: {actionable}",
        f"- Immediately executed a local task: {acted/actionable:.1%}",
        f"- Deferred it with movement/PASS: {deferred/actionable:.1%}", "",
        "## Choice when several local tasks are available", "",
        "| Available tasks | N | Most common decisions | Local-task rate |", "|---|---:|---|---:|",
    ]
    for key, counts in sorted(choices.items(), key=lambda item: -sum(item[1].values())):
        total = sum(counts.values())
        if total < 100: continue
        task_set = set(key.split("+")); local = sum(n for op, n in counts.items() if op in task_set)
        top = ", ".join(f"{op} {n/total:.1%}" for op, n in counts.most_common(5))
        lines.append(f"| {key} | {total} | {top} | {local/total:.1%} |")
    lines += ["", "## Timing signatures", "", "| Action | Top hours | Top actor indices |", "|---|---|---|"]
    for op in ("FEED", "CARE", "COLLECT_FERTILIZER", "HARVEST", "WATER", "FERTILIZE", "PLANT", "DROP", "PICKUP"):
        hours = ", ".join(f"h{h}:{n}" for h, n in hour_actions[op].most_common(6))
        actors = ", ".join(f"a{a}:{n}" for a, n in actor_actions[op].most_common(6))
        lines.append(f"| {op} | {hours} | {actors} |")
    lines += ["", "## Dominant decisions by tile class", "", "| Tile | N | Decisions |", "|---|---:|---|"]
    for key, counts in sorted(tile_actions.items(), key=lambda item: -sum(item[1].values())):
        total = sum(counts.values()); top = ", ".join(f"{op} {n/total:.1%}" for op, n in counts.most_common(5))
        lines.append(f"| {key} | {total} | {top} |")
    args.report.write_text("\n".join(lines) + "\n")
    print(f"wrote {args.report} and {args.json_output}")


if __name__ == "__main__":
    main()

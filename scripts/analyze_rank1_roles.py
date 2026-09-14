#!/usr/bin/env python3
"""Summarize rank-1 worker roles and spatial assignments by herd mode and phase."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import json
from pathlib import Path


LIVESTOCK = {"FEED", "CARE", "COLLECT_FERTILIZER"}
CROP = {"WATER", "FERTILIZE", "PLANT", "DIG"}
LOGISTICS = {"PICKUP", "DROP", "PLACE"}


def phase(day):
    if day <= 5: return "d00-05"
    if day <= 9: return "d06-09"
    if day <= 17: return "d10-17"
    if day <= 27: return "d18-27"
    return "d28-29"


def tile_class(tile):
    if not isinstance(tile, dict): return "empty/locked"
    if tile.get("animal"): return "animal"
    if tile.get("kind") == "PLANT": return "plant"
    return str(tile.get("kind", "other")).lower()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--adaptation", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    labels = {int(row["episode_id"]): row["mode"] for row in json.loads(args.adaptation.read_text())}
    stats = defaultdict(lambda: {"ops": Counter(), "groups": Counter(), "coords": Counter(), "tiles": Counter()})
    with gzip.open(args.dataset, "rt", encoding="utf-8") as source:
        for line in source:
            row = json.loads(line)
            if row.get("type") != "example": continue
            mode = labels.get(int(row["episode"]), "unknown")
            obs = row["observation"]; day = int(obs["day"]); seat = int(row["seat"])
            farm = obs["farms"][seat]
            positions = [farm["farmer"], *(farm.get("hands") or [])]
            action = row.get("action") or {}
            commands = [action.get("farmer") or ["PASS"], *(action.get("hands") or [])]
            for actor, pos in enumerate(positions):
                command = commands[actor] if actor < len(commands) else ["PASS"]
                op = command[0] if command else "PASS"; x, y = map(int, pos)
                tile = farm["tiles"][y][x]
                group = "livestock" if op in LIVESTOCK else "crop" if op in CROP else "logistics" if op in LOGISTICS else "movement/pass"
                if op == "HARVEST": group = "livestock" if tile_class(tile) == "animal" else "crop"
                value = stats[(mode, phase(day), actor)]
                value["ops"][op] += 1; value["groups"][group] += 1; value["tiles"][tile_class(tile)] += 1
                if group != "movement/pass": value["coords"][(x, y)] += 1
    lines = ["# Rank-1 worker role and region assignments", "",
             "Rows below use aligned observations/actions. Productive coordinates exclude movement and PASS.", ""]
    for mode in ("cow-heavy", "sheep-heavy"):
        for p in ("d06-09", "d10-17", "d18-27"):
            lines += [f"## {mode}, {p}", "", "| Actor | N | livestock | crop | logistics | Top operations | Top productive coordinates |", "|---:|---:|---:|---:|---:|---|---|"]
            for actor in range(16):
                value = stats.get((mode, p, actor))
                if not value: continue
                groups = value["groups"]; total = sum(groups.values())
                if total < 100: continue
                ops = ", ".join(f"{name}:{count}" for name, count in value["ops"].most_common(4))
                coords = ", ".join(f"{xy}:{count}" for xy, count in value["coords"].most_common(4))
                lines.append(f"| {actor} | {total} | {groups['livestock']/total:.1%} | {groups['crop']/total:.1%} | {groups['logistics']/total:.1%} | {ops} | {coords} |")
            lines.append("")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {args.report}")


if __name__ == "__main__":
    main()

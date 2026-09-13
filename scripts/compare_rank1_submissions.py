#!/usr/bin/env python3
"""Compare conditional behavior summaries from two rank-1 submissions."""

from __future__ import annotations

import argparse
from collections import defaultdict
import gzip
import json
from pathlib import Path
from statistics import mean


ACTIONS = (
    "HIRE", "BUY_LAND", "BUY_ANIMAL_COW", "BUY_ANIMAL_SHEEP",
    "BUY_ANIMAL_GOOSE", "BUY_SEED_WHEAT", "BUY_SEED_STRAWBERRY",
    "BUY_SEED_CARROT", "SELL_MILK", "SELL_WOOL", "SELL_WHEAT",
)
PHASES = ("d00-05", "d06-09", "d10-17", "d18-27", "d28-29")


def pct(value: float) -> str:
    return f"{value:.2%}"


def daily_profiles(path: Path) -> dict[int, dict[str, float]]:
    last: dict[tuple[int, int], dict] = {}
    with gzip.open(path, "rt", encoding="utf-8") as source:
        for line in source:
            row = json.loads(line)
            day = int(row["features"]["day"])
            key = (int(row["episode"]), day)
            if key not in last or int(row["step"]) > int(last[key]["step"]):
                last[key] = row
    by_day: dict[int, list[dict]] = defaultdict(list)
    for (_, day), row in last.items():
        by_day[day].append(row["features"])
    names = ("hands", "land", "pasture", "cow", "sheep", "goose", "wheat_tiles",
             "strawberry_tiles", "carrot_tiles", "money")
    return {day: {name: mean(float(row.get(name, 0)) for row in rows) for name in names}
            for day, rows in by_day.items()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old", type=Path, required=True)
    parser.add_argument("--new", type=Path, required=True)
    parser.add_argument("--old-dataset", type=Path)
    parser.add_argument("--new-dataset", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    old = json.loads(args.old.read_text())
    new = json.loads(args.new.read_text())

    lines = ["# Rank-1 submission behavior comparison", "",
             "The two submissions are kept separate; the older games are not mixed into the primary teacher.", "",
             "| Version | Submission | Games | Win rate | Mean reward | Mean margin |",
             "|---|---:|---:|---:|---:|---:|",
             f"| Previous | {old['submission_id']} | {old['games']} | {old['wins']/old['games']:.1%} | "
             f"{old.get('mean_reward', 0):.0f} | {old.get('mean_margin', 0):+.0f} |",
             f"| Current | {new['submission_id']} | {new['games']} | {new['wins']/new['games']:.1%} | "
             f"{new.get('mean_reward', 0):.0f} | {new.get('mean_margin', 0):+.0f} |", "",
             "## Requested market actions per game", "",
             "| Action | Previous | Current | Delta |",
             "|---|---:|---:|---:|"]
    for action in ACTIONS:
        old_rate = old.get("market", {}).get(action, {}).get("turns", 0) / old["games"]
        new_rate = new.get("market", {}).get(action, {}).get("turns", 0) / new["games"]
        lines.append(f"| {action} | {old_rate:.2f} | {new_rate:.2f} | {new_rate-old_rate:+.2f} |")

    lines += ["", "## Action-rate changes by phase", "",
              "Positive values mean the current submission requests the action more often.", "",
              "| Phase | Action | Previous | Current | Delta (pp) |",
              "|---|---|---:|---:|---:|"]
    changes = []
    for phase in PHASES:
        for action in ACTIONS[:8]:
            a = old.get("phase_rates", {}).get(phase, {}).get(action, 0)
            b = new.get("phase_rates", {}).get(phase, {}).get(action, 0)
            changes.append((abs(b-a), phase, action, a, b))
    for _, phase, action, a, b in sorted(changes, reverse=True)[:30]:
        lines.append(f"| {phase} | {action} | {pct(a)} | {pct(b)} | {(b-a)*100:+.2f} |")

    lines += ["", "## Cow/sheep response changes by phase and MILK-WOOL spread", "",
              "| Phase / spread | N prev | Cow prev→cur | Sheep prev→cur |",
              "|---|---:|---:|---:|"]
    keys = sorted(set(old.get("phase_spread_rates", {})) | set(new.get("phase_spread_rates", {})))
    for key in keys:
        a = old.get("phase_spread_rates", {}).get(key, {})
        b = new.get("phase_spread_rates", {}).get(key, {})
        if not a or not b:
            continue
        lines.append(f"| {key} | {a['observations']} | {pct(a['buy_cow'])}→{pct(b['buy_cow'])} | "
                     f"{pct(a['buy_sheep'])}→{pct(b['buy_sheep'])} |")

    if args.old_dataset and args.new_dataset:
        old_days = daily_profiles(args.old_dataset)
        new_days = daily_profiles(args.new_dataset)
        lines += ["", "## Executed farm-profile changes", "",
                  "Current minus previous, measured from the last observed state of each day.", "",
                  "| Day | Hands | Land | Pasture | Cow | Sheep | Goose | Wheat tiles | Strawberry | Carrot | Money |",
                  "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for day in range(30):
            a = old_days.get(day, {}); b = new_days.get(day, {})
            names = ("hands", "land", "pasture", "cow", "sheep", "goose", "wheat_tiles",
                     "strawberry_tiles", "carrot_tiles", "money")
            values = [b.get(name, 0) - a.get(name, 0) for name in names]
            lines.append(f"| {day} | " + " | ".join(f"{value:+.1f}" for value in values) + " |")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines) + "\n")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Create beginner-friendly CSV and Markdown summaries using only Python stdlib."""

from __future__ import annotations

from collections import Counter, defaultdict
import csv
import gzip
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "rank1_compact_features_actions.jsonl.gz"
OUT = ROOT / "analysis_output"


def op(command):
    return command[0] if isinstance(command, list) and command else "PASS"


def main():
    action_by_day = defaultdict(Counter)
    market_by_day = defaultdict(Counter)
    actor_ops = defaultdict(Counter)
    games = set()
    opponents = Counter()
    rows = 0
    with gzip.open(DATA, "rt", encoding="utf-8") as source:
        for line in source:
            row = json.loads(line)
            if row.get("type") == "metadata":
                continue
            rows += 1
            games.add(int(row["episode"]))
            opponents[row.get("opponent", "unknown")] += 1
            day = int(row["features"]["day"])
            action = row.get("action") or {}
            commands = [action.get("farmer") or ["PASS"], *(action.get("hands") or [])]
            for actor, command in enumerate(commands):
                name = op(command)
                action_by_day[day][name] += 1
                actor_ops[actor][name] += 1
            for command in action.get("market") or []:
                market_by_day[day][op(command)] += 1

    OUT.mkdir(exist_ok=True)
    write_counter_csv(OUT / "actions_by_day.csv", "day", action_by_day)
    write_counter_csv(OUT / "market_by_day.csv", "day", market_by_day)
    write_counter_csv(OUT / "actors.csv", "actor", actor_ops)

    total_actions = sum((counter for counter in action_by_day.values()), Counter())
    total_market = sum((counter for counter in market_by_day.values()), Counter())
    lines = [
        "# Quick analysis summary", "",
        f"- aligned examples: {rows:,}",
        f"- games: {len(games)}",
        f"- opponents: {len(opponents)}", "",
        "## Farmer/hand action frequency", "",
        "| action | count |", "|---|---:|",
    ]
    lines += [f"| {name} | {count:,} |" for name, count in total_actions.most_common()]
    lines += ["", "## Market action frequency", "", "| action | count |", "|---|---:|"]
    lines += [f"| {name} | {count:,} |" for name, count in total_market.most_common()]
    lines += ["", "## Most represented opponents", "", "| opponent | examples |", "|---|---:|"]
    lines += [f"| {name} | {count:,} |" for name, count in opponents.most_common(20)]
    (OUT / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Read {rows:,} aligned examples from {len(games)} games")
    print(f"Wrote summaries to {OUT}")


def write_counter_csv(path, key_name, rows):
    columns = sorted({name for counter in rows.values() for name in counter})
    with path.open("w", newline="", encoding="utf-8-sig") as target:
        writer = csv.DictWriter(target, fieldnames=[key_name, *columns])
        writer.writeheader()
        for key in sorted(rows):
            writer.writerow({key_name: key, **rows[key]})


if __name__ == "__main__":
    main()

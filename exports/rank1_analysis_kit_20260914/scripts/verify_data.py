#!/usr/bin/env python3
"""Verify the packaged datasets and print their schema/cardinality."""

from __future__ import annotations

import gzip
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_GAMES = 255
EXPECTED_EXAMPLES = 183_345


def scan(path, full):
    games = set()
    examples = 0
    metadata = None
    with gzip.open(path, "rt", encoding="utf-8") as source:
        for number, line in enumerate(source, 1):
            row = json.loads(line)
            if row.get("type") == "metadata":
                metadata = row
                continue
            required = {"episode", "step", "action"}
            required.add("observation" if full else "features")
            missing = required - row.keys()
            if missing:
                raise ValueError(f"{path.name}:{number}: missing {sorted(missing)}")
            games.add(int(row["episode"]))
            examples += 1
    if len(games) != EXPECTED_GAMES or examples != EXPECTED_EXAMPLES:
        raise ValueError(f"{path.name}: games={len(games)}, examples={examples}")
    return metadata, len(games), examples


def main():
    files = [
        (ROOT / "data" / "rank1_compact_features_actions.jsonl.gz", False),
        (ROOT / "data" / "rank1_full_observations_actions.jsonl.gz", True),
    ]
    for path, full in files:
        metadata, games, examples = scan(path, full)
        print(f"OK {path.name}: {games} games, {examples:,} aligned examples")
        if metadata:
            print(f"   metadata={metadata}")
    print("All packaged datasets passed verification.")


if __name__ == "__main__":
    main()

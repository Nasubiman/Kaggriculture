#!/usr/bin/env python3
"""Paired win/margin differences for day-six correction-gate holdouts."""

import argparse
import json
from collections import defaultdict
from pathlib import Path


def load(path):
    return {
        (row["model"], row["seed"], row["seat"]): row
        for row in json.loads(path.read_text())["games"]
        if not row.get("error")
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", type=Path)
    parser.add_argument("variant", type=Path)
    parser.add_argument("--shops", type=Path, default=Path("server-results/route_search/seed_shops3.json"))
    parser.add_argument("--gate", choices=("fert", "carrot"), required=True)
    args = parser.parse_args()
    shops = json.loads(args.shops.read_text())
    base, variant = load(args.base), load(args.variant)
    demand = {"BRUNCH_SPOT", "ICE_CREAM_SHOP", "SMOOTHIE_SHOP", "FARMERS_MARKET"}
    buckets = defaultdict(list)
    for key in base.keys() & variant.keys():
        pair = shops[str(key[1])][:2]
        active = "YARN_STORE" not in pair and sum(shop in demand for shop in pair) >= 2
        if args.gate == "carrot":
            active = "YARN_STORE" not in pair and sum(shop in demand for shop in pair) <= 1
        b, v = base[key], variant[key]
        buckets["all"].append((b, v))
        buckets["active" if active else "inactive"].append((b, v))
        if active:
            buckets[key[0]].append((b, v))
    for group, rows in sorted(buckets.items()):
        n = len(rows)
        gained = sum(v["win"] and not b["win"] for b, v in rows)
        lost = sum(b["win"] and not v["win"] for b, v in rows)
        delta_margin = sum(v["margin"] - b["margin"] for b, v in rows) / n
        changed = sum(v["reward"] != b["reward"] or v["opponent_reward"] != b["opponent_reward"] for b, v in rows)
        print(f"{group:40s} n={n:4d} base_w={sum(b['win'] for b, _ in rows):4d} "
              f"net={gained-lost:+4d} (+{gained}/-{lost}) dMargin={delta_margin:+8.1f} changed={changed}")


if __name__ == "__main__":
    main()

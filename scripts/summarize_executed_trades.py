#!/usr/bin/env python3
"""Group averages of executed_trades.py output."""
from __future__ import annotations

import argparse
import json
from collections import defaultdict

ITEMS = ["WOOL", "MILK", "STRAWBERRY", "MELON", "EGG", "TOMATO", "CARROT", "FERTILIZER", "WHEAT"]
PHASES = ["d0-11", "d12-19", "d20-26", "d27-29"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    a = ap.parse_args()
    rows = json.load(open(a.input))
    groups = defaultdict(list)
    for r in rows:
        groups[r["label"]].append(r)
    labels = sorted(groups)
    avg = lambda xs: sum(xs) / len(xs) if xs else 0.0

    def line(name, fn, fmt="%12.0f"):
        print("%-28s" % name + "".join(fmt % avg([fn(r) for r in groups[l]]) for l in labels))

    print("%-28s" % "metric" + "".join("%12s" % f"{l[:9]}({len(groups[l])})" for l in labels))
    line("reward", lambda r: r["reward"])
    for it in ITEMS:
        if it == "WHEAT":
            line("WHEAT net sold (sold-bought)", lambda r: r["sold"].get("WHEAT", 0) - r["bought"].get("WHEAT", 0))
            continue
        line(f"{it} sold", lambda r, it=it: r["sold"].get(it, 0))
        line(f"{it} revenue", lambda r, it=it: r["revenue"].get(it, 0))
        # price computed over all units of the group
        print("%-28s" % f"{it} avg price" + "".join(
            "%12.1f" % (sum(r["revenue"].get(it, 0) for r in groups[l]) / max(1, sum(r["sold"].get(it, 0) for r in groups[l])))
            for l in labels))
        line(f"{it} sell turns", lambda r, it=it: r["sell_turns"].get(it, 0))
    line("FERTILIZER bought", lambda r: r["bought"].get("FERTILIZER", 0))
    print("\npremium (WOOL+MILK+STRAWBERRY+MELON+EGG+TOMATO) units sold by phase:")
    for ph in PHASES:
        line(f"  {ph}", lambda r, ph=ph: sum(r["phase"].get(ph, {}).get(i, 0) for i in ITEMS[:6]))


if __name__ == "__main__":
    main()

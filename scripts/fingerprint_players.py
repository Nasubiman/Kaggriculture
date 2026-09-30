#!/usr/bin/env python3
"""Behavioural fingerprints of selected players from public replays.

Input: JSON list of [label, replay_path, player_index]. For each player we
record hands/quadrants/animals by day, units sold and mean price per item,
revenue per item, when premium goods were sold, and the final reward. Prints
per-group averages so groups of players can be compared.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict

PREMIUM = ("WOOL", "MILK", "STRAWBERRY", "MELON", "EGG")


def fingerprint(path, p):
    d = json.load(open(path))
    S = d["steps"]
    fp = {"reward": d["rewards"][p], "opp_reward": d["rewards"][1 - p]}
    for day in (6, 9, 12, 15, 18, 24):
        o = S[min(day * 24, len(S) - 1)][0]["observation"]
        f = o["farms"][p]
        fp[f"hands_d{day}"] = len(f.get("hands") or [])
        fp[f"quad_d{day}"] = len(f["unlocked_quadrants"])
        c = Counter(t.get("animal") for r in f["tiles"] for t in r if isinstance(t, dict) and t.get("animal"))
        for a in ("COW", "SHEEP", "GOOSE"):
            fp[f"{a}_d{day}"] = c[a]
        fp[f"money_d{day}"] = f["money"]
        plants = Counter(t.get("crop") for r in f["tiles"] for t in r if isinstance(t, dict) and t.get("kind") == "PLANT")
        for crop in ("WHEAT", "CARROT", "STRAWBERRY", "MELON", "TOMATO"):
            fp[f"{crop}_plants_d{day}"] = plants[crop]
    units = Counter(); rev = Counter(); prem_by_phase = Counter(); sell_orders = 0
    for t in range(len(S) - 1):
        prices = S[t][0]["observation"]["market"]["prices"]
        for o in (S[t + 1][p].get("action") or {}).get("market") or []:
            if o and o[0] == "SELL" and len(o) > 2:
                n = int(o[2]); units[o[1]] += n; rev[o[1]] += prices[o[1]] * n; sell_orders += 1
                if o[1] in PREMIUM:
                    phase = "early(<d12)" if t < 288 else ("mid(d12-20)" if t < 480 else "late(d20+)")
                    prem_by_phase[phase] += n
    fp["sell_orders"] = sell_orders
    for k in set(units) | set(rev):
        fp[f"units_{k}"] = units[k]; fp[f"rev_{k}"] = rev[k]
        fp[f"price_{k}"] = rev[k] / units[k] if units[k] else 0
    for k in ("early(<d12)", "mid(d12-20)", "late(d20+)"):
        fp[f"prem_{k}"] = prem_by_phase[k]
    return fp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--players", required=True)
    ap.add_argument("--output")
    a = ap.parse_args()
    groups = defaultdict(list)
    for label, path, p in json.load(open(a.players)):
        try:
            groups[label].append(fingerprint(path, int(p)))
        except Exception as e:
            print("skip", path, e)
    keys = sorted({k for g in groups.values() for fp in g for k in fp})
    labels = sorted(groups)
    print("%-26s" % "metric" + "".join("%16s" % f"{l}(n={len(groups[l])})" for l in labels))
    for k in keys:
        vals = []
        for l in labels:
            xs = [fp.get(k, 0) for fp in groups[l]]
            vals.append(sum(xs) / len(xs) if xs else 0)
        if max(abs(v) for v in vals) < 1e-9:
            continue
        print("%-26s" % k + "".join("%16.1f" % v for v in vals))
    if a.output:
        json.dump(groups, open(a.output, "w"))


if __name__ == "__main__":
    main()

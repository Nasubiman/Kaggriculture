#!/usr/bin/env python3
"""Summarize how results31-family players first deviate from results31."""
from __future__ import annotations

import argparse
import csv
import io
import json
import zipfile
from collections import Counter


def board(path):
    zf = zipfile.ZipFile(path)
    rows = csv.DictReader(io.TextIOWrapper(zf.open(zf.namelist()[0]), encoding="utf-8-sig"))
    return {r["TeamName"]: (int(r["Rank"]), float(r["Score"])) for r in rows}


def sells(orders):
    return {o[1]: int(o[2]) for o in orders if o and o[0] == "SELL" and len(o) > 2}


def other(orders):
    return sorted(tuple(o[:2]) for o in orders if o and o[0] != "SELL")


def describe(d):
    ps, as_ = sells(d["pred_market"]), sells(d["actual_market"])
    parts = []
    for item in sorted(set(ps) | set(as_)):
        if ps.get(item, 0) != as_.get(item, 0):
            parts.append(f"{item} r31={ps.get(item, 0)} them={as_.get(item, 0)}")
    po, ao = other(d["pred_market"]), other(d["actual_market"])
    if po != ao:
        parts.append(f"other r31={po} them={ao}")
    if not d["units_same"]:
        parts.append("units differ")
    return parts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", required=True)
    ap.add_argument("--board", required=True)
    ap.add_argument("--rank-min", type=int, default=380)
    ap.add_argument("--rank-max", type=int, default=508)
    a = ap.parse_args()
    rk = board(a.board)
    rows = [r for r in json.load(open(a.rows)) if r["open_match"] >= 0.75]
    kinds = Counter()
    items = Counter()
    days = Counter()
    for r in sorted(rows, key=lambda r: rk.get(r["team"], (9999,))[0]):
        rank = rk.get(r["team"], (None,))[0]
        if not rank or not (a.rank_min <= rank <= a.rank_max):
            continue
        fd = r.get("first_divs") or []
        if not fd:
            print(f"#{rank:4d} {r['team'][:22]:22s} identical to results31 all game")
            kinds["identical"] += 1
            continue
        d = fd[0]
        desc = describe(d)
        day, hour = divmod(d["step"], 24)
        days[day] += 1
        for p in desc:
            key = p.split(" r31=")[0]
            if key not in ("units differ",):
                direction = ""
                if " r31=" in p and key != "other":
                    rv = int(p.split(" r31=")[1].split()[0])
                    tv = int(p.split("them=")[1])
                    direction = "sells MORE" if tv > rv else "sells LESS"
                items[f"{key} {direction}".strip()] += 1
            else:
                items[key] += 1
        print(f"#{rank:4d} {r['team'][:22]:22s} day{day:2d} h{hour:2d}: " + "; ".join(desc)[:160])
    print("\nfirst-divergence day histogram:", dict(sorted(days.items())))
    print("what they change first:", items.most_common(20))


if __name__ == "__main__":
    main()

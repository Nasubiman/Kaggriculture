#!/usr/bin/env python3
"""Split paired screening results (variant vs base) by the seed's first shops.

Shows, per shop class, how many wins each variant gains over the base per 100
paired games, so a class-dependent constant can be spotted without new games.
"""
import argparse, json
from collections import defaultdict
from pathlib import Path

STRAW = ("BRUNCH_SPOT", "ICE_CREAM_SHOP", "SMOOTHIE_SHOP", "FARMERS_MARKET")
MILK = ("PIZZA_SHOP", "ICE_CREAM_SHOP", "SMOOTHIE_SHOP")


def classes(shops):
    s3 = sum(x in STRAW for x in shops[:3])
    m3 = sum(x in MILK for x in shops[:3])
    return {
        "straw3=0-1": s3 <= 1, "straw3=2": s3 == 2, "straw3=3": s3 == 3,
        "milk3=0": m3 == 0, "milk3>=1": m3 >= 1,
        "yarn3": "YARN_STORE" in shops[:3], "no_yarn3": "YARN_STORE" not in shops[:3],
    }


p = argparse.ArgumentParser()
p.add_argument("dirs", nargs="+", type=Path)
p.add_argument("--shops", type=Path, default=Path("server-results/seed_shops3_screen_seeds.json"))
p.add_argument("--variants", nargs="*", default=[])
p.add_argument("--exclude", nargs="*", default=["results28_20260925"], help="opponents left out (mirrors)")
a = p.parse_args()
shops = json.loads(a.shops.read_text())
names = list(classes(["BAKERY"] * 3))
for d in a.dirs:
    base = {(g["model"], g["seed"], g["seat"]): g for g in json.loads((d / "base.json").read_text())["games"] if g["model"] not in a.exclude}
    cnt = defaultdict(int)
    for (m, s, seat) in base:
        for k, v in classes(shops[str(s)]).items():
            cnt[k] += v
    print(f"== {d.name}  (paired games per class: " + ", ".join(f"{k} {cnt[k]}" for k in names) + ")")
    print(f"{'variant':26s}" + "".join(f"{k:>12s}" for k in names) + "   (wins gained per 100 games)")
    for f in sorted(d.glob("*.json")):
        if f.stem == "base" or (a.variants and f.stem not in a.variants):
            continue
        games = json.loads(f.read_text())["games"]
        gain = defaultdict(float); n = defaultdict(int)
        for g in games:
            b = base.get((g["model"], g["seed"], g["seat"]))
            if not b:
                continue
            for k, v in classes(shops[str(g["seed"])]).items():
                if v:
                    gain[k] += int(g["win"]) - int(b["win"]); n[k] += 1
        print(f"{f.stem[:26]:26s}" + "".join(f"{100*gain[k]/max(1,n[k]):+12.1f}" for k in names))

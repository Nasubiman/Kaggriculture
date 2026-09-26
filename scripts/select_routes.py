#!/usr/bin/env python3
"""Pick, per shop pair, a tape that beats the native one on identical games.

Only games whose observed step-144 shop pair matches the searched pair count.
A route replaces the native one when it wins more paired games than it loses
(by --min-net) and its mean margin is not worse.
"""
import argparse, json
from collections import defaultdict
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("results", type=Path)
p.add_argument("--min-net", type=int, default=3, help="minimum (wins gained - wins lost) vs native")
p.add_argument("--output", type=Path)
a = p.parse_args()
rows = [r for r in json.loads(a.results.read_text()) if not r.get("error") and r.get("seen_pair") == r["pair"]]
by = defaultdict(dict)
for r in rows:
    by["|".join(r["pair"])].setdefault(r["route"], {})[(r["seed"], r["seat"], r["opponent"])] = r
choice, total_gain = {}, 0
print(f"{'pair':36s} {'native W':>8s} {'best':>5s} {'W':>4s} {'net':>4s} {'dMargin':>8s}")
for pair, routes in sorted(by.items()):
    native = routes.get(None, {})
    if not native:
        continue
    best = None
    for route, games in routes.items():
        if route is None:
            continue
        keys = [k for k in games if k in native]
        gained = sum(1 for k in keys if games[k]["win"] and not native[k]["win"])
        lost = sum(1 for k in keys if native[k]["win"] and not games[k]["win"])
        dm = sum(games[k]["margin"] - native[k]["margin"] for k in keys) / max(1, len(keys))
        score = (gained - lost, dm)
        if best is None or score > best[1]:
            best = (route, score, sum(games[k]["win"] for k in keys))
    nw = sum(r["win"] for r in native.values())
    route, (net, dm), w = best
    take = net >= a.min_net and dm >= 0
    if take:
        choice[pair] = route
        total_gain += net
    print(f"{pair:36s} {nw:4d}/{len(native):<3d} {str(route):>5s} {w:4d} {net:+4d} {dm:+8.0f} {'TAKE' if take else ''}")
print("pairs changed", len(choice), "net wins gained", total_gain)
if a.output:
    a.output.write_text(json.dumps(choice, indent=1))

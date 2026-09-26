#!/usr/bin/env python3
"""Classify shop pairs as strong or weak for the current main.py.

Reads a route_search.py result that played only the native route against a
fixed opponent pool and writes {pair: {route, status, win_rate, ...}}.
"strong" pairs keep their current tape; "weak" pairs are searched next.
"""
import argparse, json
from collections import defaultdict
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("results", type=Path)
p.add_argument("--threshold", type=float, default=0.90)
p.add_argument("--candidate", default="main.py", help="to record each pair's native route")
p.add_argument("--output", type=Path)
a = p.parse_args()

ns = {}
exec(compile(Path(a.candidate).read_text(), a.candidate, "exec"), ns)
R108, R110, V92 = ns["_R108_SHOP_ROUTES"], ns["_R110_OLD_SHOPS"], ns["_V92_TABLE"]


def native(pair):
    s = tuple(pair)
    r = R108.get(s, 100) if s.count("YARN_STORE") <= 0 else R110.get(s, 0)
    return V92.get(s, r)


rows = [r for r in json.loads(a.results.read_text()) if not r.get("error") and r.get("seen_pair") == r["pair"]]
by = defaultdict(list)
for r in rows:
    by["|".join(r["pair"])].append(r)
table = {}
print(f"{'pair':36s} {'route':>5s} {'games':>5s} {'win%':>6s} {'margin':>8s}  losses by opponent")
for key in sorted(by, key=lambda k: sum(x["win"] for x in by[k]) / len(by[k])):
    g = by[key]
    wr = sum(x["win"] for x in g) / len(g)
    margin = sum(x["margin"] for x in g) / len(g)
    losses = defaultdict(int)
    for x in g:
        if not x["win"]:
            losses[x["opponent"].replace("_20260925", "").replace("_20260923", "").replace("_20260924", "")] += 1
    status = "strong" if wr >= a.threshold else "weak"
    table[key] = {"route": native(key.split("|")), "status": status, "win_rate": round(wr, 3),
                  "mean_margin": round(margin), "games": len(g)}
    print(f"{key:36s} {table[key]['route']:5d} {len(g):5d} {100*wr:5.1f}% {margin:+8.0f}  {dict(losses)} {status.upper() if status == 'weak' else ''}")
weak = [k for k, v in table.items() if v["status"] == "weak"]
print(f"strong {len(table) - len(weak)} / weak {len(weak)} (threshold {a.threshold:.0%})")
if a.output:
    a.output.write_text(json.dumps(table, indent=1, ensure_ascii=False))

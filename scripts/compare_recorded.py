#!/usr/bin/env python3
"""Compare recorded (post-correction) tapes with the native tape on identical games."""
import json, sys
from collections import defaultdict

native = json.load(open(sys.argv[1]))
rec = json.load(open(sys.argv[2]))
key = lambda r: ("|".join(r["pair"]), r["seed"], r["seat"], r["opponent"])
ok = lambda r: not r.get("error") and r.get("seen_pair") == r["pair"]
base = {key(r): r for r in native if ok(r)}
by = defaultdict(list)
for r in rec:
    if ok(r) and key(r) in base:
        by[("|".join(r["pair"]), r["route"])].append((r, base[key(r)]))
print(f"{'pair':34s} {'tape':>5s} {'games':>5s} {'native win%':>11s} {'recorded win%':>13s} {'diff':>6s} {'dMargin':>8s}")
tot = defaultdict(lambda: [0, 0, 0, 0.0])
for (pair, route), g in sorted(by.items()):
    n = len(g); wr = sum(a["win"] for a, _ in g) / n; wn = sum(b["win"] for _, b in g) / n
    dm = sum(a["margin"] - b["margin"] for a, b in g) / n
    print(f"{pair:34s} {route:5d} {n:5d} {100*wn:10.1f}% {100*wr:12.1f}% {100*(wr-wn):+5.1f} {dm:+8.0f}")
    t = tot[pair]; t[0] += n; t[1] += sum(a["win"] for a, _ in g); t[2] += sum(b["win"] for _, b in g); t[3] += dm * n
allg = sum(t[0] for t in tot.values())
print(f"ALL recorded tapes: native {100*sum(t[2] for t in tot.values())/allg:.1f}% -> recorded {100*sum(t[1] for t in tot.values())/allg:.1f}% over {allg} games, dMargin {sum(t[3] for t in tot.values())/allg:+.0f}")

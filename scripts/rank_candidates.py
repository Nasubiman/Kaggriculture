#!/usr/bin/env python3
"""Rank whole-agent candidates screened on one shop pair (screen_on_seeds output dir)."""
import json, sys
from collections import defaultdict
from pathlib import Path
d = Path(sys.argv[1])
rows = []
for f in sorted(d.glob("*.json")):
    G = [g for g in json.loads(f.read_text())["games"] if not g.get("error")]
    by = defaultdict(int)
    for g in G:
        by[g["model"]] += g["win"]
    rows.append((sum(g["win"] for g in G), f.stem, len(G), sum(g["margin"] for g in G) / max(1, len(G)), dict(by)))
rows.sort(reverse=True)
models = sorted({m for r in rows for m in r[4]})
print(f"{'candidate':40s} {'wins':>8s} {'margin':>7s}  " + " ".join(m[:10] for m in models))
for w, n, g, m, by in rows:
    print(f"{n[:40]:40s} {w:4d}/{g:<3d} {m:+7.0f}  " + " ".join(f"{by.get(x,0):>10d}" for x in models))

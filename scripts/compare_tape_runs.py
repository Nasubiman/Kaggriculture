#!/usr/bin/env python3
"""Compare candidates on identical money-pinned tape games against a base run."""
import json, sys
from pathlib import Path
base_f, *others = sys.argv[1:]
key = lambda g: (g["episode"], g["team"], g.get("tape_seat"))
base = {key(g): g for g in json.loads(Path(base_f).read_text())["games"] if not g.get("error")}
bw = sum(g["win"] for g in base.values())
print(f"{'candidate':28s} {'wins':>9s} {'gained':>7s} {'lost':>5s} {'dMargin':>8s}")
print(f"{Path(base_f).stem:28s} {bw:4d}/{len(base):<4d}")
for f in others:
    G = {key(g): g for g in json.loads(Path(f).read_text())["games"] if not g.get("error")}
    ks = [k for k in G if k in base]
    w = sum(G[k]["win"] for k in ks); gained = sum(1 for k in ks if G[k]["win"] and not base[k]["win"])
    lost = sum(1 for k in ks if base[k]["win"] and not G[k]["win"])
    dm = sum(G[k]["margin"] - base[k]["margin"] for k in ks) / max(1, len(ks))
    print(f"{Path(f).stem:28s} {w:4d}/{len(ks):<4d} {gained:+7d} {-lost:5d} {dm:+8.0f}")

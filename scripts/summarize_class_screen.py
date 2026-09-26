#!/usr/bin/env python3
"""Per shop class, rank screened variants by paired wins gained over the base."""
import json, sys
from pathlib import Path

d = Path(sys.argv[1]); seeds_dir = Path(sys.argv[2])
cls = {k: set(json.loads((seeds_dir / f"class_{k}_seeds.json").read_text())) for k in ("Y", "L", "H")}
label = {"Y": "YARN あり", "L": "苺の需要店0-1 (YARNなし)", "H": "苺の需要店2+ (YARNなし)"}
load = lambda f: {(g["model"], g["seed"], g["seat"]): g for g in json.loads(f.read_text())["games"] if not g.get("error")}
base = load(d / "base.json")
runs = {f.stem: load(f) for f in d.glob("*.json") if f.stem != "base"}
for k in ("Y", "L", "H"):
    keys = [x for x in base if x[1] in cls[k]]
    bw = sum(base[x]["win"] for x in keys)
    print(f"== {label[k]}: base {bw}/{len(keys)} ({100*bw/len(keys):.1f}%)")
    rows = []
    for name, r in runs.items():
        ks = [x for x in keys if x in r]
        if not ks:
            continue
        gained = sum(1 for x in ks if r[x]["win"] and not base[x]["win"])
        lost = sum(1 for x in ks if base[x]["win"] and not r[x]["win"])
        dm = sum(r[x]["margin"] - base[x]["margin"] for x in ks) / len(ks)
        rows.append((gained - lost, dm, name, gained, lost))
    for net, dm, name, g, l in sorted(rows, reverse=True):
        print(f"   {name:14s} net {net:+4d} (+{g}/-{l})  dMargin {dm:+7.0f}")

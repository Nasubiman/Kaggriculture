#!/usr/bin/env python3
"""Rank screened variants against the base run on identical (opponent, seed, seat) games."""
import json, sys
from pathlib import Path

d = Path(sys.argv[1])
runs = {p.stem: json.loads(p.read_text()) for p in d.glob("*.json")}
base = {(g["model"], g["seed"], g["seat"]): g for g in runs["base"]["games"]} if "base" in runs else {}
rows = []
for name, r in runs.items():
    games = r["games"]
    wins = sum(g["win"] for g in games)
    losses = sum(1 for g in games if not g["win"] and not g["tie"])
    margin = sum(g["margin"] for g in games) / len(games)
    delta = [g["margin"] - base[k]["margin"] for g in games if (k := (g["model"], g["seed"], g["seat"])) in base]
    per = {m: s["wins"] for m, s in r["summaries"].items()}
    rows.append((wins, -losses, margin, name, sum(delta) / max(1, len(delta)), per, len(games)))
rows.sort(reverse=True)
models = sorted(rows[0][5])
print(f"{'variant':34s} {'W':>4s} {'L':>4s} {'margin':>8s} {'dMargin':>8s} " + " ".join(m[:9] for m in models))
for w, nl, m, name, dm, per, n in rows:
    print(f"{name:34s} {w:4d} {-nl:4d} {m:+8.0f} {dm:+8.0f} " + " ".join(f"{per[x]:>9d}" for x in models))

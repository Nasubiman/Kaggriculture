#!/usr/bin/env python3
"""Summarize classify_mirror_replays.py output joined with leaderboard ranks."""
from __future__ import annotations

import argparse
import csv
import io
import json
import zipfile
from collections import Counter, defaultdict


def board(path):
    zf = zipfile.ZipFile(path)
    rows = csv.DictReader(io.TextIOWrapper(zf.open(zf.namelist()[0]), encoding="utf-8-sig"))
    return {r["TeamName"]: (int(r["Rank"]), float(r["Score"])) for r in rows}


def kind(r):
    if r["open_match"] < 0.75:
        return "other"
    d = r["first_divergence"]
    if d is None:
        return "exact"
    if d == 0 or r["open_match"] < 0.999:
        return "old/sibling"
    if d < 160:
        return "day6-route"
    return "late-diverge"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", required=True)
    ap.add_argument("--board", required=True)
    ap.add_argument("--rank-min", type=int, default=31)
    ap.add_argument("--rank-max", type=int, default=508)
    a = ap.parse_args()
    rows = json.load(open(a.rows))
    rk = board(a.board)
    seen = {}
    for r in rows:
        rank = rk.get(r["team"], (None, None))[0]
        r["rank"] = rank
        key = r["team"]
        if key not in seen or (r["open_match"] > seen[key]["open_match"]):
            seen[key] = r
    band = [r for r in seen.values() if r["rank"] and a.rank_min <= r["rank"] <= a.rank_max]
    print(f"players={len(rows)} unique_teams={len(seen)} in_band={len(band)}")
    by = Counter(kind(r) for r in band)
    print("family breakdown (in band):", dict(by))
    buckets = defaultdict(Counter)
    for r in band:
        b = f"{(r['rank'] - 1) // 100 * 100 + 1}-{(r['rank'] - 1) // 100 * 100 + 100}"
        buckets[b][kind(r)] += 1
    for b in sorted(buckets, key=lambda s: int(s.split('-')[0])):
        print(f"  rank {b:9s}", dict(buckets[b]))
    print("\nresults31-family teams (in band), by rank:")
    for r in sorted((r for r in band if kind(r) != "other"), key=lambda r: r["rank"]):
        print(f"  #{r['rank']:3d} {r['team'][:24]:24s} {kind(r):12s} open={r['open_match']:.2f} full={r['full_match']:.2f} "
              f"div={r['first_divergence']} sell_diff={dict(list(r['sell_diff'].items())[:4])}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Summarize a team's public submission replays without copying full observations."""

from __future__ import annotations

import argparse
import glob
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean


def operations(action):
    if not isinstance(action, dict):
        return Counter(), Counter()
    work = Counter()
    sales = Counter()
    for item in [action.get("farmer"), *(action.get("hands") or [])]:
        if item:
            work[str(item[0])] += 1
    for item in action.get("market") or []:
        if not item:
            continue
        work[str(item[0])] += 1
        if item[0] == "SELL" and len(item) > 1:
            sales[str(item[1])] += int(item[2]) if len(item) > 2 else 1
    return work, sales


def summarize(path: Path, team: str):
    replay = json.loads(path.read_text(encoding="utf-8"))
    names = replay["info"]["TeamNames"]
    seat = names.index(team)
    opponent = 1 - seat
    steps = replay["steps"]
    mine = Counter()
    theirs = Counter()
    my_sales = Counter()
    their_sales = Counter()
    for step in steps:
        for index, work, sales in ((seat, mine, my_sales),
                                   (opponent, theirs, their_sales)):
            add_work, add_sales = operations(step[index].get("action"))
            work.update(add_work)
            sales.update(add_sales)

    def snapshot(index):
        state = steps[min(index, len(steps) - 1)][seat]
        farms = state["observation"]["farms"]
        return {
            "margin": round(float(farms[seat]["money"]) - float(farms[opponent]["money"])),
            "money": round(float(farms[seat]["money"])),
            "opponent_money": round(float(farms[opponent]["money"])),
            "hands": len(farms[seat]["hands"]),
            "opponent_hands": len(farms[opponent]["hands"]),
            "quadrants": len(farms[seat]["unlocked_quadrants"]),
            "opponent_quadrants": len(farms[opponent]["unlocked_quadrants"]),
        }

    rewards = [float(value) for value in replay["rewards"]]
    margin = rewards[seat] - rewards[opponent]
    return {
        "episode": int(replay["info"]["EpisodeId"]),
        "seed": int(replay["info"]["seed"]),
        "opponent": names[opponent],
        "seat": seat,
        "result": "win" if margin > 0 else "loss" if margin < 0 else "tie",
        "reward": rewards[seat],
        "opponent_reward": rewards[opponent],
        "margin": margin,
        "shops": steps[min(144, len(steps) - 1)][seat]["observation"]["town"]["unlocked_shops"][:2],
        "timeline": {str(i): snapshot(i) for i in (143, 287, 431, 575, 719)},
        "work": dict(mine),
        "opponent_work": dict(theirs),
        "sales": dict(my_sales),
        "opponent_sales": dict(their_sales),
        "status": steps[-1][seat]["status"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replays", required=True, help="glob for episode-*-replay.json")
    parser.add_argument("--team", default="nasubiman")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    games = [summarize(Path(path), args.team) for path in sorted(glob.glob(args.replays))]
    if not games:
        parser.error("no replays matched")
    groups = defaultdict(list)
    for game in games:
        groups[tuple(game["shops"])].append(game)
    report = {
        "team": args.team,
        "games": games,
        "overall": {
            "games": len(games),
            "wins": sum(g["result"] == "win" for g in games),
            "losses": sum(g["result"] == "loss" for g in games),
            "ties": sum(g["result"] == "tie" for g in games),
            "mean_margin": mean(g["margin"] for g in games),
        },
        "by_shops": [
            {"shops": list(shops), "games": len(members),
             "wins": sum(g["result"] == "win" for g in members),
             "losses": sum(g["result"] == "loss" for g in members),
             "mean_margin": mean(g["margin"] for g in members)}
            for shops, members in sorted(groups.items())
        ],
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report["overall"], ensure_ascii=False))
    for game in sorted(games, key=lambda row: row["margin"])[:10]:
        print(game["episode"], game["result"], game["margin"],
              game["opponent"], game["shops"],
              [game["timeline"][str(i)]["margin"] for i in (143, 287, 431, 575, 719)])


if __name__ == "__main__":
    main()

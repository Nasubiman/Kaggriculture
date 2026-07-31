#!/usr/bin/env python3
"""Summarize strategies visible in collected public Kaggriculture replays."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def numeric_arg(action: list[Any], index: int = 2, default: int = 1) -> int:
    if len(action) <= index:
        return default
    try:
        return int(action[index])
    except (TypeError, ValueError):
        return default


def summarize_game(path: Path, expected_team: str) -> dict[str, Any]:
    replay = json.loads(path.read_text(encoding="utf-8"))
    team_names = replay["info"]["TeamNames"]
    try:
        player = team_names.index(expected_team)
    except ValueError as error:
        raise ValueError(f"{expected_team!r} is not in {path.name}: {team_names}") from error

    operations: Counter[str] = Counter()
    seeds: Counter[str] = Counter()
    planted: Counter[str] = Counter()
    sold: Counter[str] = Counter()
    animals: Counter[str] = Counter()
    first_day: dict[str, int] = {}
    max_hands = 0

    for turn in replay["steps"][1:]:
        state = turn[player]
        observation = state.get("observation") or {}
        day = int(observation.get("day", 0))
        farms = observation.get("farms") or []
        if player < len(farms):
            max_hands = max(max_hands, len(farms[player].get("hands", [])))

        action = state.get("action") or {}
        unit_actions = [action.get("farmer")] + list(action.get("hands") or [])
        for unit_action in unit_actions:
            if not unit_action:
                continue
            operation = str(unit_action[0])
            operations[operation] += 1
            first_day.setdefault(operation, day)
            if operation == "PLANT" and len(unit_action) > 1:
                crop = str(unit_action[1])
                planted[crop] += 1
                first_day.setdefault(f"PLANT_{crop}", day)

        for market_action in action.get("market") or []:
            if not market_action:
                continue
            operation = str(market_action[0])
            operations[operation] += 1
            first_day.setdefault(operation, day)
            if operation == "BUY_SEED" and len(market_action) > 1:
                crop = str(market_action[1])
                seeds[crop] += numeric_arg(market_action)
                first_day.setdefault(f"BUY_SEED_{crop}", day)
            elif operation == "SELL" and len(market_action) > 1:
                product = str(market_action[1])
                sold[product] += numeric_arg(market_action)
            elif operation == "BUY_ANIMAL" and len(market_action) > 1:
                animal = str(market_action[1])
                animals[animal] += numeric_arg(market_action)
                first_day.setdefault(f"BUY_ANIMAL_{animal}", day)

    rewards = [float(value) for value in replay["rewards"]]
    opponent = team_names[1 - player]
    return {
        "episode_id": int(replay["info"]["EpisodeId"]),
        "team": expected_team,
        "player": player,
        "opponent": opponent,
        "seed": int(replay["info"]["seed"]),
        "reward": rewards[player],
        "opponent_reward": rewards[1 - player],
        "win": rewards[player] > rewards[1 - player],
        "operations": operations,
        "seeds": seeds,
        "planted": planted,
        "sold": sold,
        "animals": animals,
        "first_day": first_day,
        "max_hands": max_hands,
    }


def avg_counter(games: list[dict[str, Any]], key: str) -> dict[str, float]:
    names = sorted({name for game in games for name in game[key]})
    return {
        name: mean(float(game[key].get(name, 0)) for game in games)
        for name in names
    }


def fmt_mix(values: dict[str, float], limit: int = 4) -> str:
    ranked = sorted(values.items(), key=lambda item: (-item[1], item[0]))
    return ", ".join(f"{name}:{value:.1f}" for name, value in ranked[:limit]) or "—"


def first_day_average(games: list[dict[str, Any]], operation: str) -> str:
    days = [game["first_day"][operation] for game in games if operation in game["first_day"]]
    return f"{mean(days):.1f}" if days else "—"


def analyze(replay_dir: Path, report_path: Path, csv_path: Path) -> None:
    manifest = json.loads((replay_dir / "manifest.json").read_text(encoding="utf-8"))
    by_team: dict[str, list[dict[str, Any]]] = defaultdict(list)
    all_games: list[dict[str, Any]] = []

    team_metadata = {team["team_name"]: team for team in manifest["teams"]}
    for team in manifest["teams"]:
        for episode in team["episodes"]:
            game = summarize_game(replay_dir / episode["replay"], team["team_name"])
            by_team[team["team_name"]].append(game)
            all_games.append(game)

    report_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "rank",
                "team",
                "episode_id",
                "player",
                "opponent",
                "seed",
                "reward",
                "opponent_reward",
                "win",
                "max_hands",
            ],
        )
        writer.writeheader()
        for game in all_games:
            writer.writerow(
                {
                    "rank": team_metadata[game["team"]]["rank"],
                    **{key: game[key] for key in writer.fieldnames if key != "rank"},
                }
            )

    lines = [
        "# Kaggriculture Public Game History Summary",
        "",
        f"- Collected: {manifest['collected_at']}",
        f"- Teams: {len(by_team)}",
        f"- Replays analyzed: {len(all_games)}",
        "- Counts below are per-game averages.",
        "",
        "## Results and macro strategy",
        "",
        "| Rank | Team | Games | Win rate | Reward | Margin | Max hands | Hires | Land buys | First hire day | First land day |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for team_name, games in sorted(
        by_team.items(), key=lambda item: team_metadata[item[0]]["rank"]
    ):
        operations = avg_counter(games, "operations")
        lines.append(
            "| {rank} | {team} | {games} | {win_rate:.0%} | {reward:.0f} | "
            "{margin:+.0f} | {hands:.1f} | {hires:.1f} | {lands:.1f} | {first_hire} | {first_land} |".format(
                rank=team_metadata[team_name]["rank"],
                team=team_name.replace("|", "\\|"),
                games=len(games),
                win_rate=mean(float(game["win"]) for game in games),
                reward=mean(game["reward"] for game in games),
                margin=mean(game["reward"] - game["opponent_reward"] for game in games),
                hands=mean(game["max_hands"] for game in games),
                hires=operations.get("HIRE", 0),
                lands=operations.get("BUY_LAND", 0),
                first_hire=first_day_average(games, "HIRE"),
                first_land=first_day_average(games, "BUY_LAND"),
            )
        )

    lines.extend(
        [
            "",
            "## Production and sales",
            "",
            "| Rank | Team | Seeds bought | Tiles planted | Products sold | Animals bought |",
            "|---:|---|---|---|---|---|",
        ]
    )
    for team_name, games in sorted(
        by_team.items(), key=lambda item: team_metadata[item[0]]["rank"]
    ):
        lines.append(
            f"| {team_metadata[team_name]['rank']} | {team_name.replace('|', '\\|')} | "
            f"{fmt_mix(avg_counter(games, 'seeds'))} | "
            f"{fmt_mix(avg_counter(games, 'planted'))} | "
            f"{fmt_mix(avg_counter(games, 'sold'))} | "
            f"{fmt_mix(avg_counter(games, 'animals'))} |"
        )

    lines.extend(
        [
            "",
            "## Field actions",
            "",
            "| Rank | Team | Move | Water | Harvest | Fertilize | Care | Feed |",
            "|---:|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for team_name, games in sorted(
        by_team.items(), key=lambda item: team_metadata[item[0]]["rank"]
    ):
        operations = avg_counter(games, "operations")
        move = sum(operations.get(direction, 0) for direction in ("NORTH", "SOUTH", "EAST", "WEST"))
        lines.append(
            f"| {team_metadata[team_name]['rank']} | {team_name.replace('|', '\\|')} | "
            f"{move:.1f} | {operations.get('WATER', 0):.1f} | "
            f"{operations.get('HARVEST', 0):.1f} | {operations.get('FERTILIZE', 0):.1f} | "
            f"{operations.get('CARE', 0):.1f} | {operations.get('FEED', 0):.1f} |"
        )

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {report_path}")
    print(f"Wrote {csv_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay-dir", type=Path, default=ROOT / "replays" / "public")
    parser.add_argument(
        "--report", type=Path, default=ROOT / "reports" / "public_history_summary.md"
    )
    parser.add_argument(
        "--csv", type=Path, default=ROOT / "reports" / "public_history_games.csv"
    )
    args = parser.parse_args()
    analyze(args.replay_dir.resolve(), args.report.resolve(), args.csv.resolve())


if __name__ == "__main__":
    main()

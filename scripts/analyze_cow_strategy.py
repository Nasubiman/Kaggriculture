#!/usr/bin/env python3
"""Extract cow strategy timing and operations from public replays."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean


ROOT = Path(__file__).resolve().parents[1]
COW_OPS = {"FEED", "CARE", "COLLECT_FERTILIZER", "HARVEST"}


def quantity(action):
    try:
        return int(action[2])
    except (IndexError, TypeError, ValueError):
        return 1


def cow_positions(observation, player):
    positions = []
    farm = observation["farms"][player]
    for y, row in enumerate(farm["tiles"]):
        for x, tile in enumerate(row):
            if isinstance(tile, dict) and tile.get("animal") == "COW":
                positions.append((x, y))
    return positions


def summarize(path, team_name):
    replay = json.loads(path.read_text(encoding="utf-8"))
    player = replay["info"]["TeamNames"].index(team_name)
    events = Counter()
    event_days = defaultdict(list)
    cow_position_counts = Counter()
    max_cows = 0
    max_hands = 0

    for step_index in range(1, len(replay["steps"])):
        before_state = replay["steps"][step_index - 1][player]
        after_state = replay["steps"][step_index][player]
        before = before_state["observation"]
        after = after_state["observation"]
        action = after_state.get("action") or {}
        day = int(before.get("day", 0))
        farm = before["farms"][player]
        positions = [farm["farmer"], *farm.get("hands", [])]
        unit_actions = [action.get("farmer"), *(action.get("hands") or [])]

        current_cows = cow_positions(after, player)
        max_cows = max(max_cows, len(current_cows))
        max_hands = max(max_hands, len(farm.get("hands", [])))

        for unit_index, unit_action in enumerate(unit_actions):
            if not unit_action or unit_index >= len(positions):
                continue
            operation = unit_action[0]
            x, y = positions[unit_index]
            tile = farm["tiles"][y][x]

            if operation == "BUILD_PASTURE":
                events["BUILD_PASTURE"] += 1
                event_days["BUILD_PASTURE"].append(day)
            elif operation == "PICKUP" and len(unit_action) > 1 and unit_action[1] == "COW":
                events["PICKUP_COW"] += quantity(unit_action)
                event_days["PICKUP_COW"].append(day)
            elif operation == "PLACE" and len(unit_action) > 1 and unit_action[1] == "COW":
                events["PLACE_COW"] += 1
                event_days["PLACE_COW"].append(day)
                cow_position_counts[(x, y)] += 1
            elif (
                operation in COW_OPS
                and isinstance(tile, dict)
                and tile.get("animal") == "COW"
            ):
                key = f"COW_{operation}"
                events[key] += 1
                event_days[key].append(day)

        for market_action in action.get("market") or []:
            if not market_action:
                continue
            operation = market_action[0]
            item = market_action[1] if len(market_action) > 1 else None
            amount = quantity(market_action)
            if operation == "BUY_ANIMAL" and item == "COW":
                events["BUY_COW"] += amount
                event_days["BUY_COW"].append(day)
            elif operation == "BUY_PRODUCT" and item == "WHEAT":
                events["BUY_WHEAT"] += amount
                event_days["BUY_WHEAT"].append(day)
            elif operation == "SELL" and item in ("MILK", "FERTILIZER"):
                events[f"SELL_{item}"] += amount
                event_days[f"SELL_{item}"].append(day)
            elif operation == "BUY_LAND":
                events["BUY_LAND"] += 1
                event_days["BUY_LAND"].append(day)
            elif operation == "HIRE":
                events["HIRE"] += 1

    rewards = [float(value) for value in replay["rewards"]]
    first = {
        event: min(days)
        for event, days in event_days.items()
        if days
    }
    return {
        "episode_id": replay["info"]["EpisodeId"],
        "team": team_name,
        "reward": rewards[player],
        "opponent_reward": rewards[1 - player],
        "events": dict(events),
        "first_day": first,
        "max_cows": max_cows,
        "max_hands": max_hands,
        "cow_positions": {
            f"{x},{y}": count
            for (x, y), count in cow_position_counts.items()
        },
    }


def average(games, field):
    return mean(float(game[field]) for game in games)


def average_event(games, event):
    return mean(float(game["events"].get(event, 0)) for game in games)


def average_first_day(games, event):
    values = [
        game["first_day"][event]
        for game in games
        if event in game["first_day"]
    ]
    return f"{mean(values):.1f}" if values else "—"


def analyze(replay_dir, output):
    manifest = json.loads(
        (replay_dir / "manifest.json").read_text(encoding="utf-8")
    )
    by_team = defaultdict(list)
    position_counts = defaultdict(Counter)
    all_games = []
    ranks = {}

    for team in manifest["teams"]:
        name = team["team_name"]
        ranks[name] = team["rank"]
        for episode in team["episodes"]:
            game = summarize(replay_dir / episode["replay"], name)
            by_team[name].append(game)
            all_games.append(game)
            position_counts[name].update(game["cow_positions"])

    lines = [
        "# Current leaders: cow strategy analysis",
        "",
        f"- Collected: {manifest['collected_at']}",
        f"- Replays: {len(all_games)}",
        "- Market quantities are submitted requests; invalid or "
        "unaffordable orders may execute for fewer units or no-op.",
        "",
        "## Scale and timing",
        "",
        "| Rank | Team | Reward | Max cows | Cow buy requests | First buy | First placed | Pastures | Max hands | Land buy requests |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for team, games in sorted(by_team.items(), key=lambda item: ranks[item[0]]):
        lines.append(
            f"| {ranks[team]} | {team} | {average(games, 'reward'):.0f} | "
            f"{average(games, 'max_cows'):.1f} | {average_event(games, 'BUY_COW'):.1f} | "
            f"{average_first_day(games, 'BUY_COW')} | {average_first_day(games, 'PLACE_COW')} | "
            f"{average_event(games, 'BUILD_PASTURE'):.1f} | {average(games, 'max_hands'):.1f} | "
            f"{average_event(games, 'BUY_LAND'):.1f} |"
        )

    lines.extend(
        [
            "",
            "## Per-game cow operations and output",
            "",
            "| Rank | Team | Feed | Care | Fertilizer collect | Milk harvest | Wheat buy requests | Milk sell requests | Fertilizer sell requests |",
            "|---:|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for team, games in sorted(by_team.items(), key=lambda item: ranks[item[0]]):
        lines.append(
            f"| {ranks[team]} | {team} | {average_event(games, 'COW_FEED'):.1f} | "
            f"{average_event(games, 'COW_CARE'):.1f} | "
            f"{average_event(games, 'COW_COLLECT_FERTILIZER'):.1f} | "
            f"{average_event(games, 'COW_HARVEST'):.1f} | "
            f"{average_event(games, 'BUY_WHEAT'):.1f} | "
            f"{average_event(games, 'SELL_MILK'):.1f} | "
            f"{average_event(games, 'SELL_FERTILIZER'):.1f} |"
        )

    lines.extend(["", "## Cow placement frequency", ""])
    for team, counts in sorted(position_counts.items(), key=lambda item: ranks[item[0]]):
        positions = ", ".join(
            f"({position})×{count}"
            for position, count in counts.most_common(12)
        )
        lines.append(f"- **{team}:** {positions or '—'}")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    raw_output = output.with_suffix(".json")
    raw_output.write_text(json.dumps(all_games, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {output}")
    print(f"Wrote {raw_output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--replay-dir",
        type=Path,
        default=ROOT / "replays" / "cow-study",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "reports" / "cow_strategy_analysis.md",
    )
    args = parser.parse_args()
    analyze(args.replay_dir.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()

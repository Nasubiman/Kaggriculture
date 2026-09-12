#!/usr/bin/env python3
"""Extract phase changes, timing, layout, and observable adaptation from rank-1 replays."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def tile_counts(farm: dict[str, Any]) -> Counter[str]:
    result: Counter[str] = Counter()
    for row in farm.get("tiles", []):
        for tile in row:
            if not isinstance(tile, dict):
                continue
            if tile.get("kind") == "PASTURE":
                result["PASTURE"] += 1
            if tile.get("animal"):
                result[str(tile["animal"])] += 1
            if tile.get("crop"):
                result[str(tile["crop"])] += 1
    return result


def corr(xs: list[float], ys: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    xm, ym = mean(xs), mean(ys)
    numerator = sum((x - xm) * (y - ym) for x, y in zip(xs, ys))
    denominator = math.sqrt(
        sum((x - xm) ** 2 for x in xs) * sum((y - ym) ** 2 for y in ys)
    )
    return numerator / denominator if denominator else 0.0


def analyze_game(path: Path, team: str) -> dict[str, Any]:
    replay = json.loads(path.read_text(encoding="utf-8"))
    player = replay["info"]["TeamNames"].index(team)
    opponent = 1 - player
    daily_actions: dict[int, Counter[str]] = defaultdict(Counter)
    action_hours: dict[str, Counter[int]] = defaultdict(Counter)
    action_positions: dict[str, Counter[str]] = defaultdict(Counter)
    daily_profile: dict[int, dict[str, float]] = {}
    daily_prices: dict[int, dict[str, float]] = {}
    daily_opponent: dict[int, Counter[str]] = {}

    for turn in replay["steps"][1:]:
        state = turn[player]
        observation = state.get("observation") or {}
        day = int(observation.get("day", 0))
        hour = int(observation.get("hour", 0))
        farms = observation.get("farms") or []
        if len(farms) <= player:
            continue
        farm = farms[player]
        action = state.get("action") or {}
        actors = [farm.get("farmer")] + list(farm.get("hands") or [])
        commands = [action.get("farmer")] + list(action.get("hands") or [])
        for position, command in zip(actors, commands):
            if not command:
                continue
            operation = str(command[0])
            daily_actions[day][operation] += 1
            action_hours[operation][hour] += 1
            if isinstance(position, (list, tuple)) and len(position) == 2:
                action_positions[operation][f"{position[0]},{position[1]}"] += 1
        for order in action.get("market") or []:
            if not order:
                continue
            operation = str(order[0])
            quantity = 1
            if operation not in ("HIRE", "BUY_LAND") and len(order) > 2:
                try:
                    quantity = int(order[2])
                except (TypeError, ValueError):
                    quantity = 1
            key = operation
            if operation in ("BUY_ANIMAL", "BUY_SEED", "SELL", "BUY_PRODUCT") and len(order) > 1:
                key += "_" + str(order[1])
            daily_actions[day][key] += quantity

        # Last observed state in a day becomes its end-of-day profile.
        counts = tile_counts(farm)
        daily_profile[day] = {
            "hands": float(len(farm.get("hands", []))),
            "money": float(farm.get("money", 0)),
            **{name: float(counts[name]) for name in ("PASTURE", "COW", "SHEEP", "GOOSE", "WHEAT", "MELON", "CARROT", "STRAWBERRY")},
        }
        prices = observation.get("market", {}).get("prices", {})
        daily_prices.setdefault(day, {name: float(prices.get(name, 0)) for name in ("MILK", "WOOL", "WHEAT", "FERTILIZER")})
        if len(farms) > opponent:
            daily_opponent[day] = tile_counts(farms[opponent])

    rewards = [float(value) for value in replay["rewards"]]
    return {
        "episode": int(replay["info"]["EpisodeId"]),
        "seat": player,
        "opponent": replay["info"]["TeamNames"][opponent],
        "reward": rewards[player],
        "margin": rewards[player] - rewards[opponent],
        "daily_actions": daily_actions,
        "action_hours": action_hours,
        "action_positions": action_positions,
        "daily_profile": daily_profile,
        "daily_prices": daily_prices,
        "daily_opponent": daily_opponent,
    }


def average(games: list[dict[str, Any]], day: int, section: str, key: str) -> float:
    return mean(float(game[section].get(day, {}).get(key, 0)) for game in games)


def render(games: list[dict[str, Any]], team: str, collected_at: str) -> str:
    lines = [
        f"# Rank-1 decision analysis: {team}",
        "",
        f"- Collected: {collected_at}",
        f"- Public games: {len(games)}",
        f"- Wins: {sum(game['margin'] > 0 for game in games)}/{len(games)}",
        f"- Mean reward / margin: {mean(game['reward'] for game in games):.0f} / {mean(game['margin'] for game in games):+.0f}",
        "- Market counts are submitted requests; farm profiles are observed executed state.",
        "",
        "## Daily executed profile",
        "",
        "| Day | Hands | Pasture | Cow | Sheep | Goose | Wheat | Melon | Carrot | Strawberry | Money |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    keys = ("hands", "PASTURE", "COW", "SHEEP", "GOOSE", "WHEAT", "MELON", "CARROT", "STRAWBERRY", "money")
    for day in range(30):
        values = [average(games, day, "daily_profile", key) for key in keys]
        lines.append("| " + str(day) + " | " + " | ".join(f"{value:.1f}" for value in values) + " |")

    event_keys = (
        "HIRE", "BUY_LAND", "BUY_ANIMAL_COW", "BUY_ANIMAL_SHEEP", "BUY_ANIMAL_GOOSE",
        "BUY_SEED_WHEAT", "BUY_SEED_MELON", "BUY_SEED_CARROT", "BUY_SEED_STRAWBERRY",
        "PLANT", "WATER", "FERTILIZE", "CARE", "FEED", "HARVEST",
    )
    lines.extend([
        "",
        "## Daily requested actions",
        "",
        "| Day | Hire | Land | Cow | Sheep | Goose | Wheat seed | Melon seed | Carrot seed | Strawberry seed | Plant | Water | Fertilize | Care | Feed | Harvest |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for day in range(30):
        values = [average(games, day, "daily_actions", key) for key in event_keys]
        if any(value > 0 for value in values):
            lines.append("| " + str(day) + " | " + " | ".join(f"{value:.1f}" for value in values) + " |")

    lines.extend(["", "## Observable adaptation", ""])
    for day in (5, 6, 8, 9, 10, 12, 15, 20):
        price_gap = [game["daily_prices"].get(day, {}).get("MILK", 0) - game["daily_prices"].get(day, {}).get("WOOL", 0) for game in games]
        own_balance = [game["daily_profile"].get(day, {}).get("COW", 0) - game["daily_profile"].get(day, {}).get("SHEEP", 0) for game in games]
        opponent_balance = [game["daily_opponent"].get(day, {}).get("COW", 0) - game["daily_opponent"].get(day, {}).get("SHEEP", 0) for game in games]
        lines.append(
            f"- Day {day}: corr(cow−sheep, milk−wool price)={corr(own_balance, price_gap):+.2f}; "
            f"corr(cow−sheep, opponent cow−sheep)={corr(own_balance, opponent_balance):+.2f}."
        )

    hour_totals: dict[str, Counter[int]] = defaultdict(Counter)
    position_totals: dict[str, Counter[str]] = defaultdict(Counter)
    for game in games:
        for operation, counts in game["action_hours"].items():
            hour_totals[operation].update(counts)
        for operation, counts in game["action_positions"].items():
            position_totals[operation].update(counts)
    lines.extend(["", "## Action timing and spatial concentration", ""])
    for operation in ("PLANT", "WATER", "FERTILIZE", "HARVEST", "CARE", "FEED"):
        hours = ", ".join(f"h{hour}:{count}" for hour, count in hour_totals[operation].most_common(5)) or "—"
        positions = ", ".join(f"({position}):{count}" for position, count in position_totals[operation].most_common(6)) or "—"
        lines.append(f"- {operation}: top hours {hours}; top actor positions {positions}.")

    lines.extend(["", "## Per-game mature profiles (day 18)", "", "| Episode | Opponent | Seat | Cow | Sheep | Goose | Pasture | Hands | Margin |", "|---:|---|---:|---:|---:|---:|---:|---:|---:|"])
    for game in sorted(games, key=lambda row: row["episode"]):
        profile = game["daily_profile"].get(18, {})
        lines.append(
            f"| {game['episode']} | {game['opponent']} | {game['seat']} | {profile.get('COW', 0):.0f} | "
            f"{profile.get('SHEEP', 0):.0f} | {profile.get('GOOSE', 0):.0f} | {profile.get('PASTURE', 0):.0f} | "
            f"{profile.get('hands', 0):.0f} | {game['margin']:+.0f} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads((args.replay_dir / "manifest.json").read_text(encoding="utf-8"))
    team = manifest["teams"][0]["team_name"]
    games = [analyze_game(args.replay_dir / episode["replay"], team) for episode in manifest["teams"][0]["episodes"]]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(games, team, manifest["collected_at"]), encoding="utf-8")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()

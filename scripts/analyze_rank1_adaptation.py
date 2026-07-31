#!/usr/bin/env python3
"""Analyze the current rank-1 agent's observable strategy switch."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def tile_counts(farm: dict[str, Any]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for row in farm["tiles"]:
        for tile in row:
            if not isinstance(tile, dict):
                continue
            if tile.get("animal"):
                counts[str(tile["animal"])] += 1
            if tile.get("crop"):
                counts[str(tile["crop"])] += 1
            if tile.get("kind") == "PASTURE":
                counts["PASTURE"] += 1
    return counts


def observation_at(
    replay: dict[str, Any], player: int, day: int, hour: int
) -> dict[str, Any]:
    for step in replay["steps"]:
        observation = step[player]["observation"]
        if observation["day"] == day and observation["hour"] == hour:
            return observation
    raise ValueError(f"missing observation at day={day}, hour={hour}")


def summarize(path: Path, team: str) -> dict[str, Any]:
    replay = json.loads(path.read_text(encoding="utf-8"))
    player = replay["info"]["TeamNames"].index(team)
    opponent = 1 - player

    maximum = Counter()
    for step in replay["steps"]:
        observation = step[player]["observation"]
        maximum |= tile_counts(observation["farms"][player])
    mode = "cow-heavy" if maximum["COW"] >= 20 else "sheep-heavy"

    decision = observation_at(replay, player, day=10, hour=0)
    prices = decision["market"]["prices"]
    opponent_counts = tile_counts(decision["farms"][opponent])
    rewards = [float(value) for value in replay["rewards"]]

    daily: dict[int, dict[str, int]] = {}
    for day in range(30):
        observations = [
            step[player]["observation"]
            for step in replay["steps"]
            if step[player]["observation"]["day"] == day
        ]
        if not observations:
            continue
        farm = observations[-1]["farms"][player]
        counts = tile_counts(farm)
        daily[day] = {
            "hands": len(farm.get("hands", [])),
            "pastures": counts["PASTURE"],
            "cows": counts["COW"],
            "sheep": counts["SHEEP"],
            "melon": counts["MELON"],
            "carrot": counts["CARROT"],
            "wheat": counts["WHEAT"],
        }

    return {
        "episode_id": int(replay["info"]["EpisodeId"]),
        "opponent": replay["info"]["TeamNames"][opponent],
        "seat": player,
        "mode": mode,
        "reward": rewards[player],
        "margin": rewards[player] - rewards[opponent],
        "max_cows": maximum["COW"],
        "max_sheep": maximum["SHEEP"],
        "milk_price_day10": int(prices["MILK"]),
        "wool_price_day10": int(prices["WOOL"]),
        "price_gap": int(prices["MILK"]) - int(prices["WOOL"]),
        "opponent_cows_day10": opponent_counts["COW"],
        "opponent_sheep_day10": opponent_counts["SHEEP"],
        "daily": daily,
    }


def render(games: list[dict[str, Any]], collected_at: str) -> str:
    rule_correct = sum(
        (
            "sheep-heavy"
            if game["milk_price_day10"] >= game["wool_price_day10"]
            else "cow-heavy"
        )
        == game["mode"]
        for game in games
    )
    wins = sum(game["margin"] > 0 for game in games)
    lines = [
        "# Rank-1 observable adaptation analysis",
        "",
        f"- Replay collection: {collected_at}",
        f"- Games: {len(games)}",
        f"- Wins: {wins}/{len(games)}",
        (
            "- Day-10 market rule accuracy: "
            f"{rule_correct}/{len(games)} "
            "(`MILK >= WOOL` → sheep-heavy, otherwise cow-heavy)"
        ),
        "",
        "## Per-game decision state",
        "",
        "| Episode | Opponent | Mode | Max cow/sheep | D10 milk | D10 wool | Gap | Opp. cow/sheep | Margin |",
        "|---:|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for game in sorted(games, key=lambda item: item["episode_id"]):
        lines.append(
            f"| {game['episode_id']} | {game['opponent']} | {game['mode']} | "
            f"{game['max_cows']}/{game['max_sheep']} | "
            f"{game['milk_price_day10']} | {game['wool_price_day10']} | "
            f"{game['price_gap']:+d} | "
            f"{game['opponent_cows_day10']}/{game['opponent_sheep_day10']} | "
            f"{game['margin']:+.0f} |"
        )

    lines.extend(
        [
            "",
            "## Average end-of-day profile",
            "",
            "| Day | Hands | Pastures | Cows | Sheep | Melon | Carrot | Wheat |",
            "|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for day in range(30):
        values = [game["daily"][day] for game in games if day in game["daily"]]
        if not values:
            continue
        lines.append(
            f"| {day} | "
            + " | ".join(
                f"{mean(value[key] for value in values):.1f}"
                for key in (
                    "hands",
                    "pastures",
                    "cows",
                    "sheep",
                    "melon",
                    "carrot",
                    "wheat",
                )
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--replay-dir",
        type=Path,
        default=ROOT / "replays" / "rank1-current",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "reports" / "rank1_current_adaptation.md",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        default=ROOT / "reports" / "rank1_current_adaptation.json",
    )
    args = parser.parse_args()

    manifest = json.loads(
        (args.replay_dir / "manifest.json").read_text(encoding="utf-8")
    )
    team = manifest["teams"][0]["team_name"]
    games = [
        summarize(args.replay_dir / episode["replay"], team)
        for episode in manifest["teams"][0]["episodes"]
    ]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        render(games, manifest["collected_at"]), encoding="utf-8"
    )
    args.json_output.write_text(
        json.dumps(games, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {args.output}")
    print(f"wrote {args.json_output}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Mine coherent strategy options and decision events from public replays.

This script intentionally does not imitate raw 720-turn actions.  It extracts
season-level strategy families and sparse change points that can become
counterfactual Option-Q candidates:

- opening composition
- labour schedule changes
- land-expansion timing
- crop-to-livestock conversion
- cow/sheep mode selection
- market-intensity and liquidation timing

Requested market quantities are recorded only as request signatures.  They are
not treated as executed quantities because Kaggriculture processes orders one
unit at a time against a shared lockstep market.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean, median
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
PRODUCTS = (
    "WHEAT",
    "CARROT",
    "TOMATO",
    "STRAWBERRY",
    "MELON",
    "EGG",
    "MILK",
    "WOOL",
    "FERTILIZER",
)
CROPS = PRODUCTS[:5]
ANIMALS = ("GOOSE", "COW", "SHEEP")


@dataclass(frozen=True)
class DailyState:
    day: int
    money: float
    opponent_money: float
    hands: int
    land: int
    counts: dict[str, int]
    prices: dict[str, float]
    market_inventory: dict[str, float]


@dataclass(frozen=True)
class DecisionEvent:
    kind: str
    day: int
    before: dict[str, Any]
    after: dict[str, Any]
    context: dict[str, float]


def _tile_counts(farm: dict[str, Any]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for row in farm.get("tiles", []) or []:
        for tile in row or []:
            if not isinstance(tile, dict):
                continue
            kind = str(tile.get("kind", ""))
            crop = tile.get("crop")
            animal = tile.get("animal")
            if crop:
                counts[str(crop)] += 1
            if animal:
                counts[str(animal)] += 1
            if kind in {"PASTURE", "COOP"}:
                counts[kind] += 1
    return counts


def _observation(state: dict[str, Any]) -> dict[str, Any]:
    return state.get("observation") or {}


def _day_end_states(replay: dict[str, Any], player: int) -> list[DailyState]:
    by_day: dict[int, dict[str, Any]] = {}
    for step in replay.get("steps", []):
        observation = _observation(step[player])
        if not observation:
            continue
        by_day[int(observation.get("day", 0))] = observation

    result = []
    for day, observation in sorted(by_day.items()):
        farms = list(observation.get("farms", []) or [])
        if player >= len(farms):
            continue
        opponent = 1 - player
        own_farm = farms[player]
        other_farm = farms[opponent] if opponent < len(farms) else {}
        market = observation.get("market", {}) or {}
        result.append(
            DailyState(
                day=day,
                money=float(own_farm.get("money", 0) or 0),
                opponent_money=float(other_farm.get("money", 0) or 0),
                hands=len(own_farm.get("hands", []) or []),
                land=len(own_farm.get("unlocked_quadrants", []) or []),
                counts=dict(_tile_counts(own_farm)),
                prices={
                    item: float((market.get("prices", {}) or {}).get(item, 0) or 0)
                    for item in PRODUCTS
                },
                market_inventory={
                    item: float(
                        (market.get("inventory", {}) or {}).get(item, 10_000)
                        or 10_000
                    )
                    for item in PRODUCTS
                },
            )
        )
    return result


def _requested_actions(replay: dict[str, Any], player: int) -> dict[str, Any]:
    operations: Counter[str] = Counter()
    market_items: Counter[str] = Counter()
    request_quantity: Counter[str] = Counter()
    by_day: dict[int, Counter[str]] = defaultdict(Counter)
    for step in replay.get("steps", [])[1:]:
        state = step[player]
        observation = _observation(state)
        day = int(observation.get("day", 0))
        action = state.get("action") or {}
        for unit_action in [action.get("farmer"), *(action.get("hands") or [])]:
            if not unit_action:
                continue
            operation = str(unit_action[0])
            operations[operation] += 1
            by_day[day][operation] += 1
        for order in action.get("market", []) or []:
            if not order:
                continue
            operation = str(order[0])
            operations[operation] += 1
            by_day[day][operation] += 1
            if len(order) >= 2:
                item = str(order[1])
                market_items[f"{operation}:{item}"] += 1
                if len(order) >= 3:
                    try:
                        request_quantity[f"{operation}:{item}"] += max(0, int(order[2]))
                    except (TypeError, ValueError):
                        pass
    return {
        "operations": dict(operations),
        "market_items": dict(market_items),
        "requested_quantity": dict(request_quantity),
        "by_day": {str(day): dict(values) for day, values in sorted(by_day.items())},
    }


def _context(state: DailyState) -> dict[str, float]:
    values = {
        "money": state.money,
        "opponent_money": state.opponent_money,
        "money_gap": state.money - state.opponent_money,
        "hands": float(state.hands),
        "land": float(state.land),
    }
    for name in (*CROPS, *ANIMALS, "PASTURE", "COOP"):
        values[f"count_{name.lower()}"] = float(state.counts.get(name, 0))
    for item in PRODUCTS:
        values[f"price_{item.lower()}"] = state.prices[item]
        values[f"market_{item.lower()}"] = state.market_inventory[item]
    values["milk_minus_wool"] = state.prices["MILK"] - state.prices["WOOL"]
    return values


def _event(
    kind: str,
    before: DailyState,
    after: DailyState,
    before_values: dict[str, Any],
    after_values: dict[str, Any],
) -> DecisionEvent:
    return DecisionEvent(
        kind=kind,
        day=after.day,
        before=before_values,
        after=after_values,
        context=_context(before),
    )


def _decision_events(states: list[DailyState]) -> list[DecisionEvent]:
    events: list[DecisionEvent] = []
    for before, after in zip(states, states[1:]):
        if after.land > before.land:
            events.append(
                _event(
                    "land_expansion",
                    before,
                    after,
                    {"land": before.land},
                    {"land": after.land},
                )
            )
        if after.hands != before.hands and abs(after.hands - before.hands) >= 2:
            events.append(
                _event(
                    "labour_step",
                    before,
                    after,
                    {"hands": before.hands},
                    {"hands": after.hands},
                )
            )

        before_animals = sum(before.counts.get(name, 0) for name in ANIMALS)
        after_animals = sum(after.counts.get(name, 0) for name in ANIMALS)
        if after_animals - before_animals >= 4:
            events.append(
                _event(
                    "livestock_expansion",
                    before,
                    after,
                    {
                        "animals": before_animals,
                        "cows": before.counts.get("COW", 0),
                        "sheep": before.counts.get("SHEEP", 0),
                    },
                    {
                        "animals": after_animals,
                        "cows": after.counts.get("COW", 0),
                        "sheep": after.counts.get("SHEEP", 0),
                    },
                )
            )

        before_crops = sum(before.counts.get(name, 0) for name in CROPS)
        after_crops = sum(after.counts.get(name, 0) for name in CROPS)
        if before_crops - after_crops >= 8 and after_animals > before_animals:
            events.append(
                _event(
                    "crop_to_livestock",
                    before,
                    after,
                    {"crops": before_crops, "animals": before_animals},
                    {"crops": after_crops, "animals": after_animals},
                )
            )

    # The final labour collapse is a useful liquidation marker even when the
    # drop is spread across two days.
    peak_hands = max((state.hands for state in states), default=0)
    for state in states:
        if state.day >= 20 and peak_hands >= 8 and state.hands <= peak_hands - 3:
            prior = max(
                (candidate for candidate in states if candidate.day < state.day),
                key=lambda candidate: candidate.day,
                default=state,
            )
            events.append(
                _event(
                    "labour_liquidation",
                    prior,
                    state,
                    {"hands": prior.hands},
                    {"hands": state.hands},
                )
            )
            break
    return events


def _strategy_family(states: list[DailyState], requests: dict[str, Any]) -> str:
    maxima: Counter[str] = Counter()
    for state in states:
        maxima |= Counter(state.counts)
    cows = maxima["COW"]
    sheep = maxima["SHEEP"]
    geese = maxima["GOOSE"]
    animals = cows + sheep + geese
    max_wheat = maxima["WHEAT"]
    market_items = Counter(requests["market_items"])
    wheat_market = market_items["BUY_PRODUCT:WHEAT"] + market_items["SELL:WHEAT"]

    if animals == 0:
        return "crop_only"
    if geese >= 8:
        return "goose_fertilizer"
    if animals >= 24 and cows >= 18:
        return "dense_cow_livestock"
    if animals >= 24 and sheep >= 12:
        return "dense_sheep_livestock"
    if cows >= max(12, 2 * sheep):
        return "cow_heavy"
    if sheep >= max(10, int(1.3 * cows)):
        return "sheep_heavy"
    if max_wheat >= 40 or wheat_market >= 100:
        return "wheat_market"
    return "mixed_hybrid"


def _opening_signature(states: list[DailyState]) -> dict[str, int]:
    if not states:
        return {}
    opening = min(states, key=lambda state: state.day)
    return {
        "hands": opening.hands,
        "land": opening.land,
        **{
            name.lower(): opening.counts.get(name, 0)
            for name in (*CROPS, *ANIMALS)
        },
    }


def summarize_game(path: Path, team: str) -> dict[str, Any]:
    replay = json.loads(path.read_text(encoding="utf-8"))
    names = list(replay["info"]["TeamNames"])
    player = names.index(team)
    opponent = 1 - player
    states = _day_end_states(replay, player)
    requests = _requested_actions(replay, player)
    rewards = [float(value) for value in replay.get("rewards", [0, 0])]
    events = _decision_events(states)
    maxima: Counter[str] = Counter()
    for state in states:
        maxima |= Counter(state.counts)
    return {
        "episode_id": int(replay["info"]["EpisodeId"]),
        "team": team,
        "opponent": names[opponent],
        "seat": player,
        "reward": rewards[player],
        "opponent_reward": rewards[opponent],
        "margin": rewards[player] - rewards[opponent],
        "family": _strategy_family(states, requests),
        "opening": _opening_signature(states),
        "maxima": dict(maxima),
        "events": [asdict(event) for event in events],
        "requests": requests,
        "daily": [asdict(state) for state in states],
    }


def _median(values: Iterable[float]) -> float | None:
    items = list(values)
    return float(median(items)) if items else None


def aggregate(games: list[dict[str, Any]], metadata: dict[str, Any]) -> dict[str, Any]:
    by_team: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for game in games:
        by_team[game["team"]].append(game)

    teams = []
    for team, subset in sorted(
        by_team.items(), key=lambda item: metadata[item[0]]["rank"]
    ):
        families = Counter(game["family"] for game in subset)
        event_days: dict[str, list[int]] = defaultdict(list)
        openings: dict[str, list[float]] = defaultdict(list)
        for game in subset:
            for key, value in game["opening"].items():
                openings[key].append(float(value))
            for event in game["events"]:
                event_days[event["kind"]].append(int(event["day"]))
        teams.append(
            {
                "rank_at_collection": metadata[team]["rank"],
                "team": team,
                "leaderboard_score": metadata[team].get("leaderboard_score"),
                "games": len(subset),
                "win_rate": mean(float(game["margin"] > 0) for game in subset),
                "mean_reward": mean(game["reward"] for game in subset),
                "mean_margin": mean(game["margin"] for game in subset),
                "families": dict(families),
                "mean_opening": {
                    key: mean(values) for key, values in sorted(openings.items())
                },
                "median_event_day": {
                    kind: _median(days) for kind, days in sorted(event_days.items())
                },
            }
        )
    return {"teams": teams, "games": games}


def render_markdown(result: dict[str, Any], manifest: dict[str, Any]) -> str:
    lines = [
        "# Expert option mining",
        "",
        f"- Collection: {manifest.get('collected_at')}",
        f"- Teams: {len(result['teams'])}",
        f"- Games: {len(result['games'])}",
        "- Market quantities are request signatures, not executed quantities.",
        "",
        "## Strategy families and change points",
        "",
        "| Rank | Team | Games | Families | Opening | Land | Livestock | Conversion | Liquidation | Mean margin |",
        "|---:|---|---:|---|---|---:|---:|---:|---:|---:|",
    ]
    for team in result["teams"]:
        family = ", ".join(
            f"{name}:{count}" for name, count in sorted(team["families"].items())
        )
        opening = team["mean_opening"]
        opening_text = (
            f"H{opening.get('hands', 0):.1f} "
            f"M{opening.get('melon', 0):.1f} "
            f"C{opening.get('carrot', 0):.1f} "
            f"W{opening.get('wheat', 0):.1f} "
            f"cow{opening.get('cow', 0):.1f}/sheep{opening.get('sheep', 0):.1f}"
        )
        days = team["median_event_day"]
        fmt = lambda name: "—" if days.get(name) is None else f"{days[name]:.1f}"
        lines.append(
            f"| {team['rank_at_collection']} | {team['team'].replace('|', '\\|')} | "
            f"{team['games']} | {family} | {opening_text} | "
            f"{fmt('land_expansion')} | {fmt('livestock_expansion')} | "
            f"{fmt('crop_to_livestock')} | {fmt('labour_liquidation')} | "
            f"{team['mean_margin']:+.0f} |"
        )

    lines.extend(
        [
            "",
            "## Intended use",
            "",
            "1. Treat repeated expert families as candidate continuation options.",
            "2. Use event contexts as candidate trigger features, not as causal proof.",
            "3. Reimplement notebook logic as explicit, licensed strategy modules.",
            "4. Counterfactually evaluate every option from the same saved state.",
            "5. Keep only options that improve held-out final margin against multiple opponents.",
            "6. Train the recurrent selector only after the option registry is stable.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--replay-dir", type=Path, default=ROOT / "replays" / "public"
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        default=ROOT / "reports" / "expert_options.json",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=ROOT / "reports" / "expert_options.md",
    )
    args = parser.parse_args()

    replay_dir = args.replay_dir.resolve()
    manifest = json.loads(
        (replay_dir / "manifest.json").read_text(encoding="utf-8")
    )
    metadata = {team["team_name"]: team for team in manifest["teams"]}
    games = []
    for team in manifest["teams"]:
        for episode in team["episodes"]:
            games.append(
                summarize_game(replay_dir / episode["replay"], team["team_name"])
            )
    result = {
        "format": "expert_option_mining_v1",
        "competition": manifest.get("competition", "kaggriculture"),
        "collected_at": manifest.get("collected_at"),
        **aggregate(games, metadata),
    }
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    args.report.write_text(render_markdown(result, manifest), encoding="utf-8")
    print(f"wrote {args.json_output}")
    print(f"wrote {args.report}")


if __name__ == "__main__":
    main()

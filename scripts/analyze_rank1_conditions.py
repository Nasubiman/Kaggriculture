#!/usr/bin/env python3
"""Build a compact state/action dataset and conditional rank-1 behavior report."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import json
from pathlib import Path
from statistics import mean, median
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FEATURES = (
    "day", "hour", "seat", "money", "hands", "land", "pasture",
    "cow", "sheep", "goose", "wheat_tiles", "carrot_tiles",
    "tomato_tiles", "strawberry_tiles", "melon_tiles", "shed_wheat",
    "shed_wool", "shed_milk", "shed_fertilizer", "price_wheat",
    "price_wool", "price_milk", "price_fertilizer", "milk_wool_spread",
    "opp_hands", "opp_cow", "opp_sheep", "opp_goose", "opp_herd_spread",
    "shops", "yarn_stores",
)
MARKET_LABELS = (
    "HIRE", "BUY_LAND", "BUY_ANIMAL_COW", "BUY_ANIMAL_SHEEP",
    "BUY_ANIMAL_GOOSE", "BUY_SEED_WHEAT", "BUY_SEED_CARROT",
    "BUY_SEED_TOMATO", "BUY_SEED_STRAWBERRY", "BUY_SEED_MELON",
    "BUY_PRODUCT_WHEAT", "SELL_WHEAT", "SELL_MILK", "SELL_WOOL",
    "SELL_FERTILIZER", "SELL_CARROT", "SELL_TOMATO", "SELL_STRAWBERRY",
    "SELL_MELON",
)
UNIT_OPS = ("PLANT", "WATER", "FERTILIZE", "CARE", "FEED", "HARVEST",
            "COLLECT_FERTILIZER", "BUILD_PASTURE", "DIG")


def q(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return float(ordered[round((len(ordered) - 1) * fraction)])


def tile_counts(farm: dict[str, Any]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for row in farm.get("tiles", []) or []:
        for tile in row:
            if not isinstance(tile, dict):
                continue
            kind = str(tile.get("kind", ""))
            if kind == "PASTURE":
                counts["pasture"] += 1
            animal = tile.get("animal")
            if animal:
                counts[str(animal).lower()] += 1
            crop = tile.get("crop")
            if crop:
                counts[f"{str(crop).lower()}_tiles"] += 1
    return counts


def market_labels(action: dict[str, Any]) -> tuple[set[str], Counter[str]]:
    labels: set[str] = set(); quantities: Counter[str] = Counter()
    for order in action.get("market", []) or []:
        if not order:
            continue
        op = str(order[0]); label = op
        if len(order) > 1:
            label = f"{op}_{order[1]}"
        labels.add(label)
        quantities[label] += int(order[2]) if len(order) > 2 else 1
    return labels, quantities


def features(obs: dict[str, Any], seat: int) -> dict[str, float]:
    farms = obs.get("farms", []) or []
    own = farms[seat]; opponent = farms[1 - seat]
    own_counts = tile_counts(own); opp_counts = tile_counts(opponent)
    private = obs.get("private", {}) or {}; shed = private.get("shed", {}) or {}
    prices = (obs.get("market", {}) or {}).get("prices", {}) or {}
    shops = (obs.get("town", {}) or {}).get("unlocked_shops", []) or []
    day = int(obs.get("day", int(obs.get("step", 0)) // 24))
    hour = int(obs.get("hour", int(obs.get("step", 0)) % 24))
    return {
        "day": day, "hour": hour, "seat": seat,
        "money": float(own.get("money", 0)), "hands": len(own.get("hands", []) or []),
        "land": sum(tile != "LOCKED" for row in own.get("tiles", []) or [] for tile in row),
        "pasture": own_counts["pasture"], "cow": own_counts["cow"],
        "sheep": own_counts["sheep"], "goose": own_counts["goose"],
        "wheat_tiles": own_counts["wheat_tiles"], "carrot_tiles": own_counts["carrot_tiles"],
        "tomato_tiles": own_counts["tomato_tiles"],
        "strawberry_tiles": own_counts["strawberry_tiles"],
        "melon_tiles": own_counts["melon_tiles"],
        "shed_wheat": float(shed.get("WHEAT", 0)), "shed_wool": float(shed.get("WOOL", 0)),
        "shed_milk": float(shed.get("MILK", 0)),
        "shed_fertilizer": float(shed.get("FERTILIZER", 0)),
        "price_wheat": float(prices.get("WHEAT", 0)), "price_wool": float(prices.get("WOOL", 0)),
        "price_milk": float(prices.get("MILK", 0)),
        "price_fertilizer": float(prices.get("FERTILIZER", 0)),
        "milk_wool_spread": float(prices.get("MILK", 0)) - float(prices.get("WOOL", 0)),
        "opp_hands": len(opponent.get("hands", []) or []), "opp_cow": opp_counts["cow"],
        "opp_sheep": opp_counts["sheep"], "opp_goose": opp_counts["goose"],
        "opp_herd_spread": opp_counts["cow"] - opp_counts["sheep"],
        "shops": len(shops), "yarn_stores": shops.count("YARN_STORE"),
    }


def phase(day: int) -> str:
    if day <= 5: return "d00-05"
    if day <= 9: return "d06-09"
    if day <= 17: return "d10-17"
    if day <= 27: return "d18-27"
    return "d28-29"


def spread_bin(value: float) -> str:
    if value <= -50: return "<=-50"
    if value <= 0: return "-49..0"
    if value <= 50: return "1..50"
    return ">50"


def opponent_bin(value: float) -> str:
    if value <= -4: return "sheep-heavy"
    if value >= 4: return "cow-heavy"
    return "balanced"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--json-output", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads((args.replay_dir / "manifest.json").read_text())
    team = manifest["teams"][0]["team_name"]
    episodes = manifest["teams"][0]["episodes"]
    total = 0; wins = 0; seats: Counter[int] = Counter(); opponents: Counter[str] = Counter()
    own_rewards: list[float] = []; margins: list[float] = []
    label_count: Counter[str] = Counter(); quantity_count: Counter[str] = Counter()
    label_features: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    phase_total: Counter[str] = Counter(); phase_actions: dict[str, Counter[str]] = defaultdict(Counter)
    spread_total: Counter[str] = Counter(); spread_actions: dict[str, Counter[str]] = defaultdict(Counter)
    opponent_total: Counter[str] = Counter(); opponent_actions: dict[str, Counter[str]] = defaultdict(Counter)
    joint_total: Counter[tuple[str, str]] = Counter()
    joint_actions: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    unit_hours: dict[str, Counter[int]] = defaultdict(Counter)
    unit_positions: dict[str, Counter[str]] = defaultdict(Counter)
    args.dataset.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(args.dataset, "wt", encoding="utf-8") as dataset:
        for index, episode in enumerate(episodes, start=1):
            replay = json.loads((args.replay_dir / episode["replay"]).read_text())
            names = replay["info"]["TeamNames"]; seat = names.index(team); seats[seat] += 1
            opponents[names[1-seat]] += 1
            rewards = [float(agent.get("reward") or 0) for agent in replay["steps"][-1]]
            wins += rewards[seat] > rewards[1-seat]
            own_rewards.append(rewards[seat]); margins.append(rewards[seat] - rewards[1-seat])
            for step in range(len(replay["steps"]) - 1):
                state = replay["steps"][step][seat]; obs = state.get("observation") or {}
                if len(obs.get("farms", []) or []) < 2:
                    continue
                action = replay["steps"][step + 1][seat].get("action") or {"farmer": ["PASS"], "hands": [], "market": []}
                x = features(obs, seat); labels, quantities = market_labels(action)
                total += 1; p = phase(int(x["day"])); s = spread_bin(x["milk_wool_spread"])
                o = opponent_bin(x["opp_herd_spread"])
                phase_total[p] += 1; spread_total[s] += 1; opponent_total[o] += 1
                joint_total[(p, s)] += 1
                for label in labels:
                    label_count[label] += 1; phase_actions[p][label] += 1
                    spread_actions[s][label] += 1; opponent_actions[o][label] += 1
                    joint_actions[(p, s)][label] += 1
                    if label in MARKET_LABELS:
                        for name in FEATURES: label_features[label][name].append(float(x[name]))
                quantity_count.update(quantities)
                commands = [action.get("farmer") or ["PASS"], *(action.get("hands") or [])]
                farm = obs["farms"][seat]
                positions = [[4, 4], *(farm.get("hands", []) or [])]
                for actor, command in enumerate(commands):
                    if not command: continue
                    op = str(command[0])
                    if op in UNIT_OPS:
                        unit_hours[op][int(x["hour"])] += 1
                        if actor < len(positions): unit_positions[op][str(tuple(positions[actor]))] += 1
                compact = {
                    "episode": int(replay["info"]["EpisodeId"]), "step": step,
                    "opponent": names[1-seat], "features": x,
                    "positions": positions, "inventories": (obs.get("private", {}) or {}).get("inventories", []),
                    "action": action,
                }
                dataset.write(json.dumps(compact, separators=(",", ":")) + "\n")
            if index % 25 == 0: print(f"processed {index}/{len(episodes)}", flush=True)

    summaries = {}
    for label in MARKET_LABELS:
        values = label_features.get(label)
        if not values: continue
        summaries[label] = {
            "turns": label_count[label], "quantity": quantity_count[label],
            "day_q10_median_q90": [q(values["day"], .1), median(values["day"]), q(values["day"], .9)],
            "top_hours": Counter(map(int, values["hour"])).most_common(4),
            "money_median": median(values["money"]),
            "own_cow_mean": mean(values["cow"]), "own_sheep_mean": mean(values["sheep"]),
            "opp_cow_mean": mean(values["opp_cow"]), "opp_sheep_mean": mean(values["opp_sheep"]),
            "milk_wool_spread_median": median(values["milk_wool_spread"]),
            "relevant_price_median": median(values.get({
                "BUY_ANIMAL_COW":"price_milk", "BUY_ANIMAL_SHEEP":"price_wool",
                "BUY_PRODUCT_WHEAT":"price_wheat", "SELL_WHEAT":"price_wheat",
                "SELL_MILK":"price_milk", "SELL_WOOL":"price_wool",
                "SELL_FERTILIZER":"price_fertilizer"}.get(label, "price_wheat"), [0])),
        }
    result = {
        "team": team, "submission_id": manifest["teams"][0]["submission_id"],
        "games": len(episodes), "wins": wins, "turns": total,
        "mean_reward": mean(own_rewards), "mean_margin": mean(margins),
        "seats": dict(seats), "opponents": dict(opponents),
        "market": summaries,
        "phase_rates": {p: {label: phase_actions[p][label]/phase_total[p] for label in MARKET_LABELS}
                        for p in phase_total},
        "spread_rates": {s: {label: spread_actions[s][label]/spread_total[s]
                             for label in ("BUY_ANIMAL_COW", "BUY_ANIMAL_SHEEP")}
                         for s in spread_total},
        "opponent_herd_rates": {o: {label: opponent_actions[o][label]/opponent_total[o]
                                    for label in ("BUY_ANIMAL_COW", "BUY_ANIMAL_SHEEP")}
                                for o in opponent_total},
        "phase_spread_rates": {
            f"{p}|{s}": {
                "observations": count,
                "buy_cow": joint_actions[(p, s)]["BUY_ANIMAL_COW"] / count,
                "buy_sheep": joint_actions[(p, s)]["BUY_ANIMAL_SHEEP"] / count,
            } for (p, s), count in joint_total.items()
        },
        "unit_timing": {op: {"top_hours": unit_hours[op].most_common(5),
                              "top_positions": unit_positions[op].most_common(6)}
                        for op in UNIT_OPS},
    }
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(result, indent=2)+"\n")
    lines = [f"# Rank-1 conditional behavior: {team}", "",
             f"- Games: {len(episodes)} ({wins} wins)", f"- State/action rows: {total}",
             f"- Seats: {dict(seats)}", f"- Distinct opponents: {len(opponents)}", "",
             "## Market action conditions", "",
             "| Action | Turns | Qty | Day q10/med/q90 | Top hours | Money med | Own C/S | Opp C/S | MILK-WOOL med | Price med |",
             "|---|---:|---:|---|---|---:|---|---|---:|---:|"]
    for label, row in summaries.items():
        d = row["day_q10_median_q90"]
        lines.append(f"| {label} | {row['turns']} | {row['quantity']} | {d[0]:.0f}/{d[1]:.0f}/{d[2]:.0f} | "
                     f"{', '.join('h'+str(h) for h,_ in row['top_hours'])} | {row['money_median']:.0f} | "
                     f"{row['own_cow_mean']:.1f}/{row['own_sheep_mean']:.1f} | "
                     f"{row['opp_cow_mean']:.1f}/{row['opp_sheep_mean']:.1f} | "
                     f"{row['milk_wool_spread_median']:.0f} | {row['relevant_price_median']:.0f} |")
    lines += ["", "## Cow/sheep purchase rate by MILK-WOOL spread", "",
              "| Spread | Observations | Buy cow | Buy sheep |", "|---|---:|---:|---:|"]
    for bucket in ("<=-50", "-49..0", "1..50", ">50"):
        if bucket not in spread_total: continue
        rates = result["spread_rates"][bucket]
        lines.append(f"| {bucket} | {spread_total[bucket]} | {rates['BUY_ANIMAL_COW']:.2%} | {rates['BUY_ANIMAL_SHEEP']:.2%} |")
    lines += ["", "## Cow/sheep purchase rate by opponent herd", "",
              "| Opponent herd | Observations | Buy cow | Buy sheep |", "|---|---:|---:|---:|"]
    for bucket in ("sheep-heavy", "balanced", "cow-heavy"):
        if bucket not in opponent_total: continue
        rates = result["opponent_herd_rates"][bucket]
        lines.append(f"| {bucket} | {opponent_total[bucket]} | {rates['BUY_ANIMAL_COW']:.2%} | {rates['BUY_ANIMAL_SHEEP']:.2%} |")
    lines += ["", "## Cow/sheep purchase rate by phase and price spread", "",
              "| Phase | Spread | Observations | Buy cow | Buy sheep |", "|---|---|---:|---:|---:|"]
    for p in ("d00-05", "d06-09", "d10-17", "d18-27", "d28-29"):
        for s in ("<=-50", "-49..0", "1..50", ">50"):
            count = joint_total[(p, s)]
            if not count: continue
            lines.append(f"| {p} | {s} | {count} | "
                         f"{joint_actions[(p,s)]['BUY_ANIMAL_COW']/count:.2%} | "
                         f"{joint_actions[(p,s)]['BUY_ANIMAL_SHEEP']/count:.2%} |")
    lines += ["", "## Market action rate by phase", "",
              "| Phase | Hire | Land | Cow | Sheep | Goose | Wheat seed | Strawberry seed | Carrot seed |",
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for p in ("d00-05", "d06-09", "d10-17", "d18-27", "d28-29"):
        if p not in phase_total: continue
        rates = result["phase_rates"][p]
        lines.append(f"| {p} | {rates['HIRE']:.2%} | {rates['BUY_LAND']:.2%} | "
                     f"{rates['BUY_ANIMAL_COW']:.2%} | {rates['BUY_ANIMAL_SHEEP']:.2%} | "
                     f"{rates['BUY_ANIMAL_GOOSE']:.2%} | {rates['BUY_SEED_WHEAT']:.2%} | "
                     f"{rates['BUY_SEED_STRAWBERRY']:.2%} | {rates['BUY_SEED_CARROT']:.2%} |")
    lines += ["", "## Unit-action timing", "",
              "| Action | Top hours | Top actor positions |", "|---|---|---|"]
    for op, row in result["unit_timing"].items():
        lines.append(f"| {op} | {', '.join('h'+str(h) for h,_ in row['top_hours'])} | "
                     f"{', '.join(pos for pos,_ in row['top_positions'])} |")
    args.report.write_text("\n".join(lines)+"\n")
    print(f"wrote {args.report}, {args.json_output}, {args.dataset}")


if __name__ == "__main__":
    main()

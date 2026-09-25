#!/usr/bin/env python3
"""Evaluate a conditional DECEM-inspired fourth-quadrant strawberry overlay.

This is a trajectory-level research candidate. It appends a compact public
SE-worker tape to our existing route only when the day-12 shop/cash gate
matches. The candidate is never written to main.py by this program.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
from collections import defaultdict
from pathlib import Path
from time import perf_counter

from kaggle_environments.agent import get_last_callable
from production_fast_kaggriculture import run_fast_episode


RETIRE_VARIANTS = {
    "early_retire18_p225": (432, 225),
    "early_retire20_p220": (480, 220),
    "early_retire22_p200": (528, 200),
    "early_retire24_p180": (576, 180),
}
SKIP_HARVEST_VARIANTS = {
    "early_skip_harvest_p180": {24: 180, 28: 150},
    "early_skip_harvest_p200": {24: 200, 28: 180},
    "early_skip_harvest_day24_p180": {24: 180},
}
STRAWBERRY_CAP_VARIANTS = {
    "early_strawberry_8": 8,
    "early_strawberry_9": 9,
    "early_strawberry_10": 10,
    "early_strawberry_11": 11,
    "early_strawberry_12": 12,
    "early_strawberry_13": 13,
    "early_strawberry_14": 14,
}
CONDITIONAL_CAP_VARIANTS = (
    "early_price_cap11_14",
    "early_cash_cap11_14",
    "early_price_cash_cap11_14",
    "early_shop_demand4_cap11_14",
)
VARIANTS = ("baseline", "ice_smoothie", "milk_two", "ice_smoothie_high_prices",
            "early_ice_smoothie_high_prices", *RETIRE_VARIANTS,
            *SKIP_HARVEST_VARIANTS, *STRAWBERRY_CAP_VARIANTS,
            "early_shop_cap11_14", *CONDITIONAL_CAP_VARIANTS)
_CANDIDATE = None
_OPPONENTS = {}
_TAPE = {}


def load_agent(path: Path):
    result = get_last_callable(path.read_text(encoding="utf-8"), path=str(path))
    if not callable(result):
        raise RuntimeError(f"no callable entry point: {path}")
    return result


def init_worker(candidate: str, opponents: dict[str, str], tape_path: str) -> None:
    global _CANDIDATE, _OPPONENTS, _TAPE
    _CANDIDATE = load_agent(Path(candidate))
    _OPPONENTS = {name: load_agent(Path(path)) for name, path in opponents.items()}
    _TAPE = json.loads(Path(tape_path).read_text(encoding="utf-8"))["tape"]


def eligible(observation, variant: str, threshold: float) -> bool:
    farm = observation["farms"][int(observation["player"])]
    if len(farm["unlocked_quadrants"]) != 3 or farm["money"] < threshold:
        return False
    shops = set((observation.get("town") or {}).get("unlocked_shops") or [])
    if variant in ("ice_smoothie", "ice_smoothie_high_prices",
                   "early_ice_smoothie_high_prices", *RETIRE_VARIANTS,
                   *SKIP_HARVEST_VARIANTS, *STRAWBERRY_CAP_VARIANTS,
                   "early_shop_cap11_14", *CONDITIONAL_CAP_VARIANTS):
        if not {"ICE_CREAM_SHOP", "SMOOTHIE_SHOP"}.issubset(shops):
            return False
        if variant in ("ice_smoothie_high_prices", "early_ice_smoothie_high_prices",
                       *RETIRE_VARIANTS, *SKIP_HARVEST_VARIANTS,
                       *STRAWBERRY_CAP_VARIANTS, "early_shop_cap11_14",
                       *CONDITIONAL_CAP_VARIANTS):
            prices = observation["market"]["prices"]
            return float(prices["STRAWBERRY"]) >= 210 and float(prices["MILK"]) >= 225
        return True
    return len(shops & {"ICE_CREAM_SHOP", "SMOOTHIE_SHOP", "PIZZA_SHOP"}) >= 2


def wrap_candidate(variant: str, threshold: float, stats: dict):
    active = False
    primed = False
    extra_workers = 0
    last_day = -1
    skip_today = False
    strawberry_plants = 0
    selected_strawberry_cap = None
    deferred_market = []

    def candidate(observation):
        nonlocal active, primed, extra_workers, last_day, skip_today
        nonlocal strawberry_plants, selected_strawberry_cap, deferred_market
        step = int(observation["step"])
        day = step // 24
        if step == 0:
            active = False
            primed = False
            extra_workers = 0
            last_day = -1
            skip_today = False
            strawberry_plants = 0
            selected_strawberry_cap = None
            deferred_market = []
        if day != last_day:
            extra_workers = 0
            last_day = day
            skip_today = False
        action = _CANDIDATE(observation)
        if variant == "baseline":
            return action
        if (variant == "early_ice_smoothie_high_prices" or variant in RETIRE_VARIANTS
                or variant in SKIP_HARVEST_VARIANTS or variant in STRAWBERRY_CAP_VARIANTS
                or variant == "early_shop_cap11_14" or variant in CONDITIONAL_CAP_VARIANTS):
            farm = observation["farms"][int(observation["player"])]
            quadrants = len(farm["unlocked_quadrants"])
            if step == 253 and quadrants == 2 and farm["money"] >= threshold:
                shops = set(observation["town"]["unlocked_shops"])
                prices = observation["market"]["prices"]
                primed = ({"ICE_CREAM_SHOP", "SMOOTHIE_SHOP"}.issubset(shops)
                          and prices["STRAWBERRY"] >= 200 and prices["MILK"] >= 220)
                if primed:
                    stats["early_open"] = 1
                    return dict(action, market=list(action.get("market") or []) + [["BUY_LAND"]])
            if primed and step == 265 and quadrants == 3:
                market = list(action.get("market") or [])
                if not any(order and order[0] == "BUY_LAND" for order in market):
                    market.append(["BUY_LAND"])
                return dict(action, market=market)
            if step == 289 and primed and quadrants == 4:
                active = True
                stats["activated"] = 1
            # A failed day-10 gate may still qualify at day 12. Let the
            # generic day-12 check below handle that one step.
            if not active and step != 289:
                return action
        if step == 289 and eligible(observation, variant, threshold):
            active = True
            stats["activated"] = 1
        retirement = RETIRE_VARIANTS.get(variant)
        if active and retirement and step == retirement[0]:
            if observation["market"]["prices"]["STRAWBERRY"] < retirement[1]:
                active = False
                stats["retired"] = 1
        if not active:
            return action
        if step == 289 and (variant == "early_shop_cap11_14"
                            or variant in CONDITIONAL_CAP_VARIANTS):
            shops = observation["town"]["unlocked_shops"]
            prices = observation["market"]["prices"]
            cash = float(observation["farms"][int(observation["player"])]["money"])
            if variant == "early_shop_cap11_14":
                high = len(shops) >= 4 and shops[3] in ("BAKERY", "FARMERS_MARKET")
            elif variant == "early_shop_demand4_cap11_14":
                strawberry_shops = {"ICE_CREAM_SHOP", "SMOOTHIE_SHOP",
                                    "BRUNCH_SPOT", "FARMERS_MARKET"}
                high = sum(shop in strawberry_shops for shop in shops) >= 4
            elif variant == "early_price_cap11_14":
                high = float(prices["STRAWBERRY"]) >= 230
            elif variant == "early_cash_cap11_14":
                high = cash >= 13_000
            else:
                high = float(prices["STRAWBERRY"]) >= 225 and cash >= 12_000
            selected_strawberry_cap = 14 if high else 11
            stats["selected_strawberry_cap"] = selected_strawberry_cap
            stats["strawberry_price_at_activation"] = float(prices["STRAWBERRY"])
            stats["cash_at_activation"] = cash
            stats["strawberry_inventory_at_activation"] = int(
                observation["market"]["inventory"]["STRAWBERRY"])
            stats["shops_at_activation"] = list(shops)
            rival = observation["farms"][1 - int(observation["player"])]
            stats["rival_strawberry_plants_at_activation"] = sum(
                isinstance(tile, dict) and tile.get("crop") == "STRAWBERRY"
                for row in rival["tiles"] for tile in row)
        skip_threshold = SKIP_HARVEST_VARIANTS.get(variant, {}).get(day)
        if skip_threshold is not None and step % 24 == 0:
            if observation["market"]["prices"]["STRAWBERRY"] < skip_threshold:
                skip_today = True
                stats["skipped_harvest_days"] = stats.get("skipped_harvest_days", 0) + 1
        if skip_today:
            return action
        row = _TAPE.get(str(step))
        if row is None and not deferred_market:
            return action
        row = row or {"hire": 0}
        market = list(action.get("market") or [])
        if deferred_market:
            market.extend(deferred_market)
            deferred_market = []
        if row.get("land"):
            farm = observation["farms"][int(observation["player"])]
            if len(farm["unlocked_quadrants"]) < 4:
                market.append(["BUY_LAND"])
        for order in row.get("buys") or []:
            order = list(order)
            cap = (selected_strawberry_cap if variant == "early_shop_cap11_14"
                   or variant in CONDITIONAL_CAP_VARIANTS
                   else STRAWBERRY_CAP_VARIANTS.get(variant))
            if cap is not None and order[:2] == ["BUY_SEED", "STRAWBERRY"]:
                order[2] = min(int(order[2]), cap)
            # The source placed these purchases at this step. In two late
            # cases the live market controller may already make the purchase,
            # especially after a one-step fertilizer deferral.
            already = sum(int(item[2]) for item in market
                          if len(item) >= 3 and item[:2] == order[:2])
            if step in (650, 697) and already >= int(order[2]):
                continue
            market.append(order)
        hires = int(row["hire"])
        market.extend([["HIRE"] for _ in range(hires)])
        # The live market layer may add a fertilizer restock that the public
        # replay placed one hour later. Keep the hires within the 10-order cap
        # and postpone only that restock, preserving its eventual quantity.
        while len(market) > 10:
            index = next((i for i in range(len(market) - 1, -1, -1)
                          if market[i][:2] == ["BUY_PRODUCT", "FERTILIZER"]), None)
            if index is None:
                break
            deferred_market.insert(0, market.pop(index))
            stats["deferred_fertilizer"] = stats.get("deferred_fertilizer", 0) + 1
        if len(market) > 10:
            stats["market_overflow"] = stats.get("market_overflow", 0) + 1
            return action
        hands = list(action.get("hands") or [])
        if extra_workers:
            commands = [list(command) for command in (row.get("hands") or [])]
            if len(commands) != extra_workers or len(hands) < extra_workers:
                stats["worker_mismatch"] = stats.get("worker_mismatch", 0) + 1
                return action
            cap = (selected_strawberry_cap if variant == "early_shop_cap11_14"
                   or variant in CONDITIONAL_CAP_VARIANTS
                   else STRAWBERRY_CAP_VARIANTS.get(variant))
            if cap is not None:
                for index, command in enumerate(commands):
                    if command == ["PLANT", "STRAWBERRY"]:
                        if strawberry_plants >= cap:
                            commands[index] = ["PASS"]
                        else:
                            strawberry_plants += 1
            hands[-extra_workers:] = commands
        extra_workers += hires
        return dict(action, hands=hands, market=market)

    return candidate


def play(task: tuple[str, str, int, int, float]) -> dict:
    variant, opponent_name, seed, seat, threshold = task
    stats = {"activated": 0}
    candidate = wrap_candidate(variant, threshold, stats)
    opponent = _OPPONENTS[opponent_name]
    agents = [candidate, opponent] if seat == 0 else [opponent, candidate]
    try:
        result = run_fast_episode(agents, seed=seed)
        ours = float(result[seat].reward)
        theirs = float(result[1 - seat].reward)
        farm = result[seat].observation["farms"][seat]
        se_plants = sum(isinstance(tile, dict) and tile.get("kind") == "PLANT"
                        for y, tiles in enumerate(farm["tiles"]) for x, tile in enumerate(tiles)
                        if x >= 5 and y >= 5)
        quadrants = len(farm["unlocked_quadrants"])
        error = None
    except Exception as exc:
        ours = theirs = 0.0
        se_plants = quadrants = 0
        error = f"{type(exc).__name__}: {exc}"
    return {"variant": variant, "opponent": opponent_name, "seed": seed,
            "seat": seat, "reward": ours, "opponent_reward": theirs,
            "margin": ours - theirs, "win": ours > theirs,
            "se_plants": se_plants, "quadrants": quadrants,
            "error": error, **stats}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, default=Path("main.py"))
    parser.add_argument("--tape", type=Path, default=Path("training/decem_se_strawberry_111847040.json"))
    parser.add_argument("--models-dir", type=Path, default=Path("test"))
    parser.add_argument("--opponents", nargs="+", required=True)
    parser.add_argument("--variants", nargs="+", choices=VARIANTS, default=VARIANTS)
    parser.add_argument("--seed-values", nargs="+", type=int)
    parser.add_argument("--seed-file", type=Path,
                        help="JSON output from find_public_four_quadrant_seeds.py")
    parser.add_argument("--activated-seed-report", type=Path,
                        help="Use unique activated seeds from a random-screen JSON report")
    parser.add_argument("--shop-filter", choices=("milk_two", "ice_smoothie", "ice_smoothie_high_prices"),
                        default="ice_smoothie")
    parser.add_argument("--seed-start", type=int, default=123_000_000)
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--min-cash", type=float, default=10_000)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.workers < 1 or args.seeds < 1:
        parser.error("workers and seeds must be positive")
    opponents = {name: str((args.models_dir / name / "main.py").resolve())
                 for name in args.opponents}
    missing = [name for name, path in opponents.items() if not Path(path).is_file()]
    if missing:
        parser.error(f"missing opponents: {missing}")
    if sum(bool(value) for value in (args.seed_values, args.seed_file,
                                    args.activated_seed_report)) > 1:
        parser.error("choose one seed source")
    if args.activated_seed_report:
        rows = json.loads(args.activated_seed_report.read_text(encoding="utf-8"))["games"]
        seeds = sorted({int(row["seed"]) for row in rows if row.get("activated")})
    elif args.seed_file:
        rows = json.loads(args.seed_file.read_text(encoding="utf-8"))["eligible"]
        seeds = [int(row["seed"]) for row in rows
                 if args.shop_filter == "milk_two" or (
                     row["ice_smoothie"] and (
                         args.shop_filter == "ice_smoothie" or (
                             row["prices"]["STRAWBERRY"] >= 210 and
                             row["prices"]["MILK"] >= 225))) ]
    else:
        seeds = args.seed_values or [args.seed_start + 17 * i for i in range(args.seeds)]
    if not seeds:
        parser.error("no matching seeds")
    tasks = [(variant, name, seed, seat, args.min_cash)
             for seed in seeds for name in args.opponents for seat in (0, 1)
             for variant in args.variants]
    started = perf_counter()
    games = []
    with mp.get_context("spawn").Pool(args.workers, initializer=init_worker,
                                       initargs=(str(args.candidate.resolve()), opponents,
                                                 str(args.tape.resolve()))) as pool:
        for index, row in enumerate(pool.imap_unordered(play, tasks, chunksize=1), 1):
            games.append(row)
            if index % 200 == 0:
                print(f"completed={index}/{len(tasks)} elapsed={perf_counter()-started:.1f}s", flush=True)
    summaries = {}
    for variant in args.variants:
        subset = [row for row in games if row["variant"] == variant]
        summaries[variant] = {"wins": sum(row["win"] for row in subset),
                              "games": len(subset),
                              "mean_margin": sum(row["margin"] for row in subset) / len(subset),
                              "mean_reward": sum(row["reward"] for row in subset) / len(subset),
                              "activations": sum(row["activated"] for row in subset),
                              "errors": sum(row["error"] is not None for row in subset),
                              "worker_mismatches": sum(row.get("worker_mismatch", 0) for row in subset),
                              "market_overflows": sum(row.get("market_overflow", 0) for row in subset)}
    output = {"source_episode": 111847040, "candidate": str(args.candidate),
              "seeds": seeds, "workers": args.workers, "min_cash": args.min_cash,
              "elapsed_seconds": perf_counter()-started, "summaries": summaries,
              "games": sorted(games, key=lambda row: (row["variant"], row["opponent"], row["seed"], row["seat"]))}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    for variant in args.variants:
        print(variant, summaries[variant], flush=True)
    print(f"wrote {args.output}", flush=True)


if __name__ == "__main__":
    main()

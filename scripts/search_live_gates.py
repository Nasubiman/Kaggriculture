#!/usr/bin/env python3
"""Paired search over the current submission's live decision thresholds.

Each worker loads the candidate and public opponents once. All variants play
the same seeds from both seats; only three module-global thresholds change.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
from collections import defaultdict
from pathlib import Path
from time import perf_counter
from typing import Any

from kaggle_environments.agent import get_last_callable

from production_fast_kaggriculture import run_fast_episode


VARIANTS: dict[str, dict[str, int | float | str]] = {
    "baseline": {},
    "ca15": {"_CA_MARGIN": -15.0, "_SR_MARGIN": 32, "_V12_LOOK": 5},
    "ca10": {"_CA_MARGIN": -10.0, "_SR_MARGIN": 32, "_V12_LOOK": 5},
    "ca17": {"_CA_MARGIN": -17.0, "_SR_MARGIN": 32, "_V12_LOOK": 5},
    "ca18": {"_CA_MARGIN": -18.0, "_SR_MARGIN": 32, "_V12_LOOK": 5},
    "ca19": {"_CA_MARGIN": -19.0, "_SR_MARGIN": 32, "_V12_LOOK": 5},
    "ca20": {"_CA_MARGIN": -20.0, "_SR_MARGIN": 32, "_V12_LOOK": 5},
    "sr24": {"_CA_MARGIN": -15.0, "_SR_MARGIN": 24, "_V12_LOOK": 5},
    "sr40": {"_CA_MARGIN": -15.0, "_SR_MARGIN": 40, "_V12_LOOK": 5},
    "look4": {"_CA_MARGIN": -15.0, "_SR_MARGIN": 32, "_V12_LOOK": 4},
    "look4_ca17": {"_CA_MARGIN": -17.0, "_SR_MARGIN": 32, "_V12_LOOK": 4},
    "ca20_sr24": {"_CA_MARGIN": -20.0, "_SR_MARGIN": 24, "_V12_LOOK": 5},
    "ca20_sr40": {"_CA_MARGIN": -20.0, "_SR_MARGIN": 40, "_V12_LOOK": 5},
    "ca20_demand": {"_CA_MARGIN": -15.0, "_SR_MARGIN": 32, "_V12_LOOK": 5},
    "ca20_pet": {"_CA_MARGIN": -15.0, "_SR_MARGIN": 32, "_V12_LOOK": 5},
    "ca20_farm": {"_CA_MARGIN": -15.0, "_SR_MARGIN": 32, "_V12_LOOK": 5},
    "ca20_early": {"_CA_MARGIN": -15.0, "_SR_MARGIN": 32, "_V12_LOOK": 5},
    "ca20_late": {"_CA_MARGIN": -15.0, "_SR_MARGIN": 32, "_V12_LOOK": 5},
    "opening_original": {"_CA_MARGIN": -15.0, "_SR_MARGIN": 32, "_V12_LOOK": 5,
                         "_ALT_MODE": "Original"},
    "opening_early": {"_CA_MARGIN": -15.0, "_SR_MARGIN": 32, "_V12_LOOK": 5,
                      "_ALT_MODE": "EarlyCycle"},
    "opening_tomato": {"_CA_MARGIN": -15.0, "_SR_MARGIN": 32, "_V12_LOOK": 5,
                       "_ALT_MODE": "TomatoInsteadOfCow"},
    "market_self": {"_MARKET_OPPONENT_WEIGHT": 0.0},
    "market_half": {"_MARKET_OPPONENT_WEIGHT": 0.5},
    "market_double": {"_MARKET_OPPONENT_WEIGHT": 2.0},
    "market_half_day20": {"_MARKET_OPPONENT_WEIGHT": 0.5, "_MARKET_FROM_STEP": 480},
    "market_half_day24": {"_MARKET_OPPONENT_WEIGHT": 0.5, "_MARKET_FROM_STEP": 576},
    "no_v13_reorder": {"_DISABLE_FUNCTION": "_v13_reorder"},
    "no_v44y_reorder": {"_DISABLE_FUNCTION": "_v44y_reorder"},
    "no_v12_advance": {"_DISABLE_FUNCTION": "_v12_advance"},
    "no_v12_frontload": {"_DISABLE_FUNCTION": "_v12_frontload"},
    "frontload_investments_only": {"_FRONTLOAD_INVESTMENTS_ONLY": True},
    "frontload_buyproduct_only": {"_FRONTLOAD_BUYPRODUCT_ONLY": True},
    "frontload_major_purchases": {"_FRONTLOAD_MAJOR_PURCHASES": True},
    "frontload_always": {"_FRONTLOAD_ALWAYS": True},
    "no_v11_overflow": {"_DISABLE_FUNCTION": "_v11_overflow"},
    "no_feed_safety": {"_ENTRY": "_FEED_SAFETY_PARENT"},
}

_MODULE = None
_AGENT = None
_OPPONENTS: dict[str, Any] = {}
_DEFAULTS: dict[str, Any] = {}
_LOCKSTEP_ORIGINAL = None
_FUNCTION_DEFAULTS: dict[str, Any] = {}


def load_raw_agent(path: Path):
    selected = get_last_callable(path.read_text(encoding="utf-8"), path=str(path))
    if not callable(selected):
        raise RuntimeError(f"{path} does not define a callable entry point")
    return selected


def load_candidate(path: Path):
    selected = load_raw_agent(path)
    # Match evaluate_test_models.py's default and Kaggle's raw-file loader.
    return selected.__globals__, selected


def worker_init(candidate: str, opponents: dict[str, str]) -> None:
    global _MODULE, _AGENT, _OPPONENTS, _DEFAULTS, _LOCKSTEP_ORIGINAL, _FUNCTION_DEFAULTS
    _MODULE, _AGENT = load_candidate(Path(candidate))
    _LOCKSTEP_ORIGINAL = _MODULE["_v44y_lockstep"]
    _FUNCTION_DEFAULTS = {key: _MODULE[key] for key in
                          ("_v13_reorder", "_v44y_reorder", "_v12_advance",
                           "_v12_frontload", "_v11_overflow")}
    _DEFAULTS = {key: _MODULE[key] for key in
                 ("_CA_MARGIN", "_SR_MARGIN", "_V12_LOOK", "_ALT_MODE")}
    _OPPONENTS = {
        name: load_raw_agent(Path(path))
        for name, path in opponents.items()
    }


def play(task: tuple[str, str, int, int]) -> dict[str, Any]:
    label, opponent_name, seed, seat = task
    assert _MODULE is not None and _AGENT is not None
    for key, value in _DEFAULTS.items():
        _MODULE[key] = value
    for key, value in _FUNCTION_DEFAULTS.items():
        _MODULE[key] = value
    _MODULE["_v44y_lockstep"] = _LOCKSTEP_ORIGINAL
    dynamic_weight = [1.0]
    candidate = _AGENT
    for key, value in VARIANTS[label].items():
        if key == "_MARKET_OPPONENT_WEIGHT":
            dynamic_weight[0] = float(value)
            def weighted_lockstep(*args, **kwargs):
                ours, theirs = _LOCKSTEP_ORIGINAL(*args, **kwargs)
                return ours, dynamic_weight[0] * theirs
            _MODULE["_v44y_lockstep"] = weighted_lockstep
        elif key == "_MARKET_FROM_STEP":
            def phase_agent(observation, _from=int(value)):
                dynamic_weight[0] = 0.5 if int(observation["step"]) >= _from else 1.0
                return _AGENT(observation)
            candidate = phase_agent
        elif key == "_DISABLE_FUNCTION":
            _MODULE[value] = lambda _observation, action: action
        elif key == "_FRONTLOAD_INVESTMENTS_ONLY":
            def selective_frontload(observation, action):
                orders = action.get("market") or []
                if any(order and order[0] in ("BUY_LAND", "BUY_ANIMAL") for order in orders):
                    return _FUNCTION_DEFAULTS["_v12_frontload"](observation, action)
                return action
            _MODULE["_v12_frontload"] = selective_frontload
        elif key == "_FRONTLOAD_BUYPRODUCT_ONLY":
            def selective_frontload(observation, action):
                orders = action.get("market") or []
                if any(order and order[0] == "BUY_PRODUCT" for order in orders):
                    return _FUNCTION_DEFAULTS["_v12_frontload"](observation, action)
                return action
            _MODULE["_v12_frontload"] = selective_frontload
        elif key == "_FRONTLOAD_MAJOR_PURCHASES":
            def selective_frontload(observation, action):
                orders = action.get("market") or []
                major = any(order and order[0] in ("BUY_LAND", "BUY_ANIMAL") for order in orders)
                major = major or sum(
                    max(0, int(order[2])) for order in orders
                    if len(order) >= 3 and order[0] == "BUY_PRODUCT"
                ) >= 20
                if major:
                    return _FUNCTION_DEFAULTS["_v12_frontload"](observation, action)
                return action
            _MODULE["_v12_frontload"] = selective_frontload
        elif key == "_FRONTLOAD_ALWAYS":
            def original_frontload(observation, action):
                market = [list(order) for order in (action.get("market") or []) if order]
                if len(market) < 2 or int(observation.get("step", 0)) < _MODULE["_V12_FROM"]:
                    return action
                bought = {order[1] for order in market if len(order) > 1 and order[0] == "BUY_PRODUCT"}
                front = [order for order in market
                         if len(order) >= 3 and order[0] == "SELL" and order[1] not in bought]
                middle = [order for order in market if (
                    len(order) >= 3 and order[0] == "BUY_PRODUCT"
                ) or (
                    len(order) >= 3 and order[0] == "SELL" and order[1] in bought
                )]
                rest = [order for order in market if order not in front and order not in middle]
                reordered = front + middle + rest
                if reordered == market:
                    return action
                _MODULE["_V12_REPORT"]["frontload_turns"] += 1
                return dict(action, market=reordered)
            _MODULE["_v12_frontload"] = original_frontload
        elif key == "_ENTRY":
            candidate = _MODULE[value]
        else:
            _MODULE[key] = value
    opponent = _OPPONENTS[opponent_name]
    if label.startswith("ca20_") and label not in ("ca20_sr24", "ca20_sr40"):
        def dynamic_agent(observation):
            shops = observation["town"]["unlocked_shops"]
            day = int(observation["step"]) // 24
            if label == "ca20_demand":
                enabled = "PET_CAFE" in shops or "FARMERS_MARKET" in shops
            elif label == "ca20_pet":
                enabled = "PET_CAFE" in shops
            elif label == "ca20_farm":
                enabled = "FARMERS_MARKET" in shops
            elif label == "ca20_early":
                enabled = day < 12
            else:
                enabled = day >= 12
            _MODULE["_CA_MARGIN"] = -20.0 if enabled else -15.0
            return _AGENT(observation)
        candidate = dynamic_agent
    agents = [candidate, opponent] if seat == 0 else [opponent, candidate]
    try:
        final = run_fast_episode(agents, seed=seed)
        ours = float(final[seat].reward)
        theirs = float(final[1 - seat].reward)
        error = None
    except Exception as exc:
        ours = theirs = 0.0
        error = f"{type(exc).__name__}: {exc}"
    return {
        "variant": label,
        "opponent": opponent_name,
        "seed": seed,
        "seat": seat,
        "reward": ours,
        "opponent_reward": theirs,
        "margin": ours - theirs,
        "win": ours > theirs,
        "error": error,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, default=Path("main.py"))
    parser.add_argument("--models-dir", type=Path, default=Path("test"))
    parser.add_argument("--opponents", nargs="+", required=True)
    parser.add_argument("--variants", nargs="+", choices=VARIANTS, default=list(VARIANTS))
    parser.add_argument("--seed-start", type=int, default=97_000_000)
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--seed-values", type=int, nargs="+",
                        help="explicit seeds, overriding --seed-start and --seeds")
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.seeds < 1 or args.workers < 1:
        parser.error("seeds and workers must be positive")
    opponents = {name: str((args.models_dir / name / "main.py").resolve())
                 for name in args.opponents}
    missing = [name for name, path in opponents.items() if not Path(path).is_file()]
    if missing:
        parser.error(f"missing opponent main.py: {missing}")

    seed_values = args.seed_values or [args.seed_start + 17 * offset for offset in range(args.seeds)]
    tasks = [(label, name, seed, seat)
             for seed in seed_values
             for name in args.opponents for seat in (0, 1)
             for label in args.variants]
    started = perf_counter()
    games = []
    context = mp.get_context("spawn")
    with context.Pool(args.workers, initializer=worker_init,
                      initargs=(str(args.candidate.resolve()), opponents)) as pool:
        for index, game in enumerate(pool.imap_unordered(play, tasks, chunksize=1), 1):
            games.append(game)
            if index % 200 == 0:
                print(f"completed={index}/{len(tasks)} elapsed={perf_counter() - started:.1f}s", flush=True)

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for game in games:
        grouped[game["variant"]].append(game)
    summaries = {}
    for label, rows in grouped.items():
        per_opponent = {}
        for name in args.opponents:
            subset = [row for row in rows if row["opponent"] == name]
            per_opponent[name] = {
                "wins": sum(row["win"] for row in subset),
                "games": len(subset),
                "mean_margin": sum(row["margin"] for row in subset) / len(subset),
                "errors": sum(row["error"] is not None for row in subset),
            }
        summaries[label] = {
            "wins": sum(row["win"] for row in rows),
            "games": len(rows),
            "mean_margin": sum(row["margin"] for row in rows) / len(rows),
            "errors": sum(row["error"] is not None for row in rows),
            "per_opponent": per_opponent,
        }
    output = {
        "candidate": str(args.candidate),
        "seed_start": args.seed_start,
        "seeds": len(seed_values),
        "seed_values": seed_values,
        "workers": args.workers,
        "variants": {label: VARIANTS[label] for label in args.variants},
        "elapsed_seconds": perf_counter() - started,
        "summaries": summaries,
        "games": sorted(games, key=lambda row: (row["variant"], row["opponent"], row["seed"], row["seat"])),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n")
    for label in args.variants:
        row = summaries[label]
        print(f"{label:12s} wins={row['wins']}/{row['games']} "
              f"margin={row['mean_margin']:+.1f} errors={row['errors']}", flush=True)
    print(f"wrote {args.output}", flush=True)


if __name__ == "__main__":
    main()

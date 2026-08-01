#!/usr/bin/env python3
"""Ablate current rank-2 market-feed and livestock choices around main.py."""

from __future__ import annotations

import argparse
import importlib.util
import json
import multiprocessing as mp
import os
from dataclasses import replace
from pathlib import Path
from typing import Any

from ev2_genome import Ev2Genome
from search_ev2_hierarchical import evaluate, worker_init


ROOT = Path(__file__).resolve().parents[1]
OPPONENTS = ("0801_ev1", "0801_ev2", "0801_ev3", "0801_v1")


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def incumbent_genome(path: Path) -> Ev2Genome:
    module = load_module(path, "rank2_ablation_incumbent")
    raw = getattr(module, "_FROZEN_EV2_GENOME", None)
    if not isinstance(raw, dict):
        raise RuntimeError(f"{path} has no _FROZEN_EV2_GENOME")
    fields = Ev2Genome.__dataclass_fields__
    return Ev2Genome(
        **{name: value for name, value in raw.items() if name in fields}
    ).normalized()


def variants(base: Ev2Genome) -> dict[str, Ev2Genome]:
    herd14 = {
        "mid_herd": 10,
        "target_herd": 14,
        "animal_slots_sw": 4,
    }
    herd15 = {
        "mid_herd": 10,
        "target_herd": 15,
        "animal_slots_sw": 5,
    }
    market_feed_light = {
        "wheat_nw": 2,
        "wheat_ne": 1,
        "wheat_sw": 1,
        "carrot_nw": 0,
        "carrot_ne": 0,
        "carrot_sw": 0,
        "feed_stock_days": 4,
    }
    market_feed_zero = {
        "wheat_nw": 0,
        "wheat_ne": 0,
        "wheat_sw": 0,
        "carrot_nw": 0,
        "carrot_ne": 0,
        "carrot_sw": 0,
        "feed_stock_days": 4,
    }
    land = {"first_land_day": 8, "second_land_day": 11}

    def changed(*blocks: dict[str, Any]) -> Ev2Genome:
        values = {}
        for block in blocks:
            values.update(block)
        return replace(base, **values).normalized()

    return {
        "incumbent": base,
        "rank2_herd14": changed(herd14),
        "rank2_herd15": changed(herd15),
        "rank2_feed_buffer4": changed({"feed_stock_days": 4}),
        "rank2_feed_buffer5": changed({"feed_stock_days": 5}),
        "rank2_market_feed_light": changed(market_feed_light),
        "rank2_market_feed_zero": changed(market_feed_zero),
        "rank2_herd14_market_feed": changed(herd14, market_feed_light),
        "rank2_herd15_market_feed": changed(herd15, market_feed_light),
        "rank2_land_8_11": changed(land),
        "rank2_static_combined": changed(herd15, market_feed_light, land),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--incumbent", type=Path, default=ROOT / "main.py")
    parser.add_argument(
        "--engine", type=Path, default=ROOT / "test/0801_ev2/main.py"
    )
    parser.add_argument("--models-dir", type=Path, default=ROOT / "test")
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--seed-start", type=int, default=9_400_000)
    parser.add_argument("--workers", type=int, default=20)
    parser.add_argument("--variants", nargs="*", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    base = incumbent_genome(args.incumbent.resolve())
    named = variants(base)
    if args.variants:
        missing = sorted(set(args.variants) - set(named))
        if missing:
            raise SystemExit("unknown variant(s): " + ", ".join(missing))
        selected = set(args.variants) | {"incumbent"}
        named = {name: genome for name, genome in named.items() if name in selected}
    opponents = {
        name: str((args.models_dir.resolve() / name / "main.py"))
        for name in OPPONENTS
    }
    seeds = [args.seed_start + index * 31 for index in range(args.seeds)]
    context = mp.get_context("spawn")
    workers = max(1, min(args.workers, os.cpu_count() or args.workers))
    with context.Pool(
        workers,
        initializer=worker_init,
        initargs=(str(args.engine.resolve()), opponents, True),
    ) as pool:
        rows = evaluate(pool, list(named.values()), list(opponents), seeds)

    names = {genome.key(): name for name, genome in named.items()}
    for row in rows:
        row["variant"] = names[row["key"]]
    rows.sort(key=lambda row: row["objective"], reverse=True)
    baseline = next(row for row in rows if row["variant"] == "incumbent")
    for row in rows:
        row["reward_delta"] = row["mean_reward"] - baseline["mean_reward"]
        row["objective_delta"] = row["objective"] - baseline["objective"]

    payload = {
        "source": {
            "leader": "radiant-allomancer",
            "leaderboard_rank": 2,
            "leaderboard_score": 1418.4,
            "public_replays": 15,
            "observed": {
                "max_hands": 12,
                "land_days": [8, 11],
                "mean_wheat_bought": 1093.9,
                "mean_wheat_sold": 806.4,
                "mean_animals": {"cows": 7.55, "sheep": 6.85},
            },
        },
        "seeds": seeds,
        "opponents": opponents,
        "results": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    for row in rows:
        print(
            f"{row['variant']:31} reward={row['mean_reward']:.1f} "
            f"delta={row['reward_delta']:+.1f} worst={row['worst_opponent_reward']:.1f} "
            f"win={row['win_rate']:.1%} errors={row['errors']}"
        )
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()

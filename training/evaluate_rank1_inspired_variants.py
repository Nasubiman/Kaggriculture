#!/usr/bin/env python3
"""Ablate current rank-1 observable macro choices around the ev2 incumbent."""

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
    module = load_module(path, "rank1_ablation_incumbent")
    raw = getattr(module, "_FROZEN_EV2_GENOME", None)
    if not isinstance(raw, dict):
        raise RuntimeError(f"{path} has no _FROZEN_EV2_GENOME")
    fields = Ev2Genome.__dataclass_fields__
    return Ev2Genome(
        **{name: value for name, value in raw.items() if name in fields}
    ).normalized()


def variants(base: Ev2Genome) -> dict[str, Ev2Genome]:
    labor = {"max_hands": 13}
    land = {"first_land_day": 8, "second_land_day": 11}
    herd = {
        "core_herd": 5,
        "mid_herd": 9,
        "target_herd": 13,
        "herd_expansion_day": 5,
        "herd_final_day": 11,
        "animal_slots_nw": 5,
        "animal_slots_ne": 5,
        "animal_slots_sw": 3,
    }
    opening_crop = {
        "wheat_nw": 11,
        "carrot_nw": 0,
        "melon_tiles_min": 9,
        "melon_tiles_base": 9,
        "melon_tiles_max": 9,
    }

    def changed(*blocks: dict[str, Any]) -> Ev2Genome:
        values = {}
        for block in blocks:
            values.update(block)
        return replace(base, **values).normalized()

    return {
        "incumbent": base,
        "rank1_labor_13": changed(labor),
        "rank1_land_8_11": changed(land),
        "rank1_herd_5_9_13": changed(herd),
        "rank1_opening_melon9_wheat11": changed(opening_crop),
        "rank1_labor_land": changed(labor, land),
        "rank1_herd_crop": changed(herd, opening_crop),
        "rank1_static_combined": changed(labor, land, herd, opening_crop),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--incumbent", type=Path, default=ROOT / "main.py")
    parser.add_argument(
        "--engine", type=Path, default=ROOT / "test/0801_ev2/main.py"
    )
    parser.add_argument("--models-dir", type=Path, default=ROOT / "test")
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--seed-start", type=int, default=9_300_000)
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
            "leader": "nishchal jain",
            "leaderboard_score": 1427.4,
            "public_replays": 15,
            "observed": {
                "max_hands": 13,
                "land_days": [8, 11],
                "opening": {"cows": 4, "pastures": 5, "melon": 9, "wheat": 11},
                "mature_herd": {"cows": 7, "sheep": 6},
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

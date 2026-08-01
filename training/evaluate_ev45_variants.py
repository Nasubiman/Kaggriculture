#!/usr/bin/env python3
"""Ablate the strategy differences exposed by strong 0801_ev4/ev5 agents."""

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
DEFAULT_OPPONENTS = (
    "0801_ev1",
    "0801_ev2",
    "0801_ev3",
    "0801_v1",
    "0801_ev4",
    "0801_ev5",
)


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def incumbent_genome(path: Path) -> Ev2Genome:
    module = load_module(path, "ev45_ablation_incumbent")
    raw = getattr(module, "_FROZEN_EV2_GENOME", None)
    if not isinstance(raw, dict):
        raise RuntimeError(f"{path} has no _FROZEN_EV2_GENOME")
    fields = Ev2Genome.__dataclass_fields__
    return Ev2Genome(
        **{name: value for name, value in raw.items() if name in fields}
    ).normalized()


def variants(base: Ev2Genome) -> dict[str, Ev2Genome]:
    def changed(**values: Any) -> Ev2Genome:
        return replace(base, **values).normalized()

    ev4_herd = {
        "core_herd": 4,
        "mid_herd": 11,
        "target_herd": 15,
        "herd_expansion_day": 7,
        "herd_final_day": 11,
        "animal_slots_nw": 4,
        "animal_slots_ne": 7,
        "animal_slots_sw": 4,
    }
    ev5_herd = {
        "core_herd": 4,
        "mid_herd": 8,
        "target_herd": 14,
        "herd_expansion_day": 7,
        "herd_final_day": 11,
        "animal_slots_nw": 4,
        "animal_slots_ne": 6,
        "animal_slots_sw": 4,
    }
    ev4_full = {
        **ev4_herd,
        "liquidation_turns": 22,
        "travel_cost": 8.0,
        "wheat_se": 5,
        "melon_tiles_min": 8,
        "fertilizer_use": 0,
        "reserve_fertilizer": 0.18,
    }
    ev5_full = {
        **ev5_herd,
        "liquidation_turns": 38,
        "travel_cost": 8.0,
        "wheat_se": 5,
        "melon_tiles_min": 8,
        "fertilizer_use": 0,
        "reserve_fertilizer": 0.18,
    }
    return {
        "incumbent": base,
        "core4": changed(core_herd=4),
        "travel8": changed(travel_cost=8.0),
        "liquidation18": changed(liquidation_turns=18),
        "liquidation20": changed(liquidation_turns=20),
        "liquidation22": changed(liquidation_turns=22),
        "liquidation24": changed(liquidation_turns=24),
        "liquidation26": changed(liquidation_turns=26),
        "liquidation28": changed(liquidation_turns=28),
        "liquidation30": changed(liquidation_turns=30),
        "liquidation32": changed(liquidation_turns=32),
        "liquidation38": changed(liquidation_turns=38),
        "fertilizer_off": changed(fertilizer_use=0, reserve_fertilizer=0.18),
        "ev4_herd": changed(**ev4_herd),
        "ev5_herd": changed(**ev5_herd),
        "herd14_current_layout": changed(
            mid_herd=10, target_herd=14, animal_slots_sw=4
        ),
        "herd15_current_layout": changed(
            mid_herd=10,
            target_herd=15,
            animal_slots_ne=6,
            animal_slots_sw=4,
        ),
        "ev4_herd_day5": changed(**{**ev4_herd, "herd_expansion_day": 5}),
        "ev5_herd_day5": changed(**{**ev5_herd, "herd_expansion_day": 5}),
        "ev4_herd_liquid22": changed(
            **{**ev4_herd, "liquidation_turns": 22}
        ),
        "ev5_herd_liquid38": changed(
            **{**ev5_herd, "liquidation_turns": 38}
        ),
        "ev4_full": changed(**ev4_full),
        "ev5_full": changed(**ev5_full),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--incumbent", type=Path, default=ROOT / "main.py")
    parser.add_argument(
        "--engine", type=Path, default=ROOT / "test/0801_ev2/main.py"
    )
    parser.add_argument("--models-dir", type=Path, default=ROOT / "test")
    parser.add_argument("--opponents", nargs="*", default=list(DEFAULT_OPPONENTS))
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--seed-start", type=int, default=9_810_000)
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
        named = {
            name: genome for name, genome in named.items() if name in selected
        }

    opponents = {
        name: str(args.models_dir.resolve() / name / "main.py")
        for name in args.opponents
    }
    missing_paths = [path for path in opponents.values() if not Path(path).is_file()]
    if missing_paths:
        raise SystemExit("missing opponent(s): " + ", ".join(missing_paths))

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
            "models": ["0801_ev4", "0801_ev5"],
            "purpose": "strong-opponent component ablation",
        },
        "seeds": seeds,
        "opponents": opponents,
        "results": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    for row in rows:
        ev4 = row["by_opponent"].get("0801_ev4", {})
        ev5 = row["by_opponent"].get("0801_ev5", {})
        print(
            f"{row['variant']:26} reward={row['mean_reward']:.1f} "
            f"delta={row['reward_delta']:+.1f} worst={row['worst_opponent_reward']:.1f} "
            f"ev4={ev4.get('win_rate', 0):.1%} "
            f"ev5={ev5.get('win_rate', 0):.1%} errors={row['errors']}"
        )
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()

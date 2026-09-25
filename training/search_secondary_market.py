#!/usr/bin/env python3
"""Search an additional product-market front-run overlay against one opponent."""

from __future__ import annotations

import argparse
from dataclasses import replace
import json
import multiprocessing as mp
import os
from pathlib import Path
import random

from current_genome import CurrentGenome, SECONDARY_ITEMS
from search_current_genomes import evaluate, read_incumbent, row, unique, worker_init
from search_wool_market import save


ROOT = Path(__file__).resolve().parents[1]


def hourly_candidates(base: CurrentGenome, slot: str) -> list[dict]:
    rows = [row(base, "incumbent")]
    blocked_item = base.secondary_item if slot == "tertiary" else "inherit"
    for item in SECONDARY_ITEMS:
        if item in ("inherit", blocked_item):
            continue
        for hour in range(24):
            genome = replace(base, **{
                f"{slot}_item": item,
                f"{slot}_start_day": 8,
                f"{slot}_end_day": 29,
                f"{slot}_sell_hour": hour,
                f"{slot}_keep": 0,
                f"{slot}_min_price": 0,
                f"{slot}_sell_cap": 0,
            })
            rows.append(row(genome, f"{item.lower()}_hour_{hour:02d}"))
    return unique(rows)


def mutate_slot(parent: CurrentGenome, rng: random.Random, slot: str) -> CurrentGenome:
    blocked_item = parent.secondary_item if slot == "tertiary" else None
    item_choices = tuple(
        item for item in SECONDARY_ITEMS if item == "inherit" or item != blocked_item
    )
    fields = {
        f"{slot}_item": item_choices,
        f"{slot}_start_day": (4, 6, 8, 10, 12, 14, 16, 20, 24),
        f"{slot}_end_day": (16, 20, 24, 26, 27, 28, 29),
        f"{slot}_sell_hour": tuple(range(24)),
        f"{slot}_keep": (0, 2, 4, 8, 12, 20),
        f"{slot}_min_price": (0, 1, 5, 20, 40, 60, 100, 150, 200),
        f"{slot}_sell_cap": (0, 1, 2, 4, 6, 8, 12, 16, 24),
    }
    values = parent.to_dict()
    for name in rng.sample(list(fields), rng.choices((1, 2, 3), (5, 3, 1))[0]):
        choices = [value for value in fields[name] if value != values[name]]
        values[name] = rng.choice(choices)
    return CurrentGenome(**values).normalized()


def expanded_candidates(
    base: CurrentGenome, parents: list[dict], count: int, rng: random.Random,
    slot: str,
) -> list[dict]:
    rows = [row(base, "incumbent")]
    rows.extend(
        row(CurrentGenome(**value["genome"]), f"parent_{index}")
        for index, value in enumerate(parents)
    )
    attempts = 0
    while len(unique(rows)) < count and attempts < count * 100:
        attempts += 1
        source = CurrentGenome(**rng.choice(parents)["genome"])
        rows.append(
            row(mutate_slot(source, rng, slot), f"{slot}_mutation_{attempts}")
        )
    return unique(rows)[:count]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=ROOT / "main.py")
    parser.add_argument("--models-dir", type=Path, default=ROOT / "test")
    parser.add_argument("--opponent", default="public_v43_competitive_20260915")
    parser.add_argument("--slot", choices=("secondary", "tertiary"), default="secondary")
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--population", type=int, default=192)
    parser.add_argument("--screen-seeds", type=int, default=8)
    parser.add_argument("--race-seeds", type=int, default=40)
    parser.add_argument("--final-seeds", type=int, default=200)
    parser.add_argument("--seed", type=int, default=2026091602)
    parser.add_argument("--seed-start", type=int, default=20_260_000)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    opponent_path = args.models_dir / args.opponent / "main.py"
    missing = [str(path) for path in (args.base, opponent_path) if not path.is_file()]
    if missing:
        raise SystemExit("missing file(s): " + ", ".join(missing))
    base = read_incumbent(args.base.resolve())
    rng = random.Random(args.seed)
    context = mp.get_context("spawn")
    workers = max(1, min(args.workers, os.cpu_count() or args.workers))
    init = (str(args.base.resolve()), {args.opponent: str(opponent_path.resolve())})

    with context.Pool(workers, initializer=worker_init, initargs=init) as pool:
        seeds0 = [args.seed_start + 31 * index for index in range(args.screen_seeds)]
        stage0 = save(
            output / "stage0_products_hours.json",
            seeds0,
            evaluate(pool, hourly_candidates(base, args.slot), [args.opponent], seeds0, base),
        )
        stage1_rows = expanded_candidates(
            base, stage0[:12], args.population, rng, args.slot
        )
        seeds1 = [args.seed_start + 100_000 + 31 * index for index in range(args.screen_seeds)]
        stage1 = save(
            output / f"stage1_{args.slot}_screen.json",
            seeds1,
            evaluate(pool, stage1_rows, [args.opponent], seeds1, base),
        )
        race_rows = [row(base, "incumbent")] + [
            row(CurrentGenome(**value["genome"]), value["label"])
            for value in stage1[:24]
        ]
        seeds2 = [args.seed_start + 200_000 + 31 * index for index in range(args.race_seeds)]
        stage2 = save(
            output / "stage2_race.json",
            seeds2,
            evaluate(pool, race_rows, [args.opponent], seeds2, base),
        )
        final_rows = [row(base, "incumbent")] + [
            row(CurrentGenome(**value["genome"]), value["label"])
            for value in stage2[:8]
        ]
        seeds3 = [args.seed_start + 300_000 + 31 * index for index in range(args.final_seeds)]
        final = save(
            output / "final_heldout.json",
            seeds3,
            evaluate(pool, final_rows, [args.opponent], seeds3, base),
        )

    incumbent = next(value for value in final if value["key"] == base.key())
    eligible = [
        value for value in final
        if value["key"] != base.key()
        and value["errors"] == 0
        and value["win_rate"] > incumbent["win_rate"]
        and value["mean_margin"] >= incumbent["mean_margin"]
        and value["mean_reward"] >= incumbent["mean_reward"]
    ]
    selected = eligible[0] if eligible else incumbent
    decision = {
        "accepted": bool(eligible),
        "objective": "win rate with non-regressing margin and own reward",
        "incumbent": incumbent,
        "selected": selected,
    }
    (output / "decision.json").write_text(json.dumps(decision, indent=2) + "\n")
    (output / "best_genome.json").write_text(
        json.dumps(selected["genome"], indent=2) + "\n"
    )
    print(
        f"decision accepted={bool(eligible)} selected={selected['label']} "
        f"wins={selected['win_rate']:.1%} margin={selected['mean_margin']:+.1f} "
        f"reward={selected['mean_reward']:.1f}",
        flush=True,
    )


if __name__ == "__main__":
    main()

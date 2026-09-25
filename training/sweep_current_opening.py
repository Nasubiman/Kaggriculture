#!/usr/bin/env python3
"""Paired opening-quantity sweep around the currently frozen genome."""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
from dataclasses import replace
from pathlib import Path

from current_genome import CurrentGenome
from search_current_genomes import evaluate, read_incumbent, row, worker_init


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=Path("main.py"))
    parser.add_argument("--models-dir", type=Path, default=Path("test"))
    parser.add_argument("--opponents", nargs="+", required=True)
    parser.add_argument("--quantities", nargs="+", type=int,
                        default=[25, 30, 35, 40, 45, 50, 55, 60])
    parser.add_argument("--modes", nargs="+",
                        choices=["roundtrip_first", "sell_buy_tail", "combined"],
                        default=["roundtrip_first"])
    parser.add_argument("--include-combinations", action="store_true",
                        help="also test q35 with uncapped wheat and earlier strawberry")
    parser.add_argument("--seeds", type=int, default=30)
    parser.add_argument("--seed-start", type=int, default=25_000_000)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    base = read_incumbent(args.base.resolve())
    variants: list[tuple[str, CurrentGenome]] = [
        (f"{mode}_{quantity}", replace(
            base, opening_roundtrip_mode=mode,
            opening_roundtrip_quantity=quantity,
        ).normalized())
        for mode in args.modes for quantity in args.quantities
    ]
    if args.include_combinations:
        variants += [
            ("roundtrip_first_35_wheat_uncapped", replace(
                base, opening_roundtrip_mode="roundtrip_first",
                opening_roundtrip_quantity=35, tertiary_sell_cap=0,
            ).normalized()),
            ("roundtrip_first_35_wheat_uncapped_strawberry21", replace(
                base, opening_roundtrip_mode="roundtrip_first",
                opening_roundtrip_quantity=35, tertiary_sell_cap=0,
                secondary_sell_hour=21,
            ).normalized()),
        ]
    candidates = [row(base, "incumbent")] + [row(g, name) for name, g in variants]
    opponents = {
        name: str((args.models_dir / name / "main.py").resolve())
        for name in args.opponents
    }
    seeds = [args.seed_start + 31 * i for i in range(args.seeds)]
    with mp.get_context("spawn").Pool(
        max(1, min(args.workers, os.cpu_count() or args.workers)),
        initializer=worker_init,
        initargs=(str(args.base.resolve()), opponents),
    ) as pool:
        results = evaluate(pool, candidates, args.opponents, seeds, base)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"seeds": seeds, "results": results}, indent=2)
                           + "\n", encoding="utf-8")
    for result in results:
        rates = " ".join(
            f"{name}={value['win_rate']:.1%}"
            for name, value in result["by_opponent"].items()
        )
        print(f"{result['label']}: delta={result['mean_delta']:+.1f} "
              f"margin={result['mean_margin_delta']:+.1f} {rates}", flush=True)


if __name__ == "__main__":
    main()

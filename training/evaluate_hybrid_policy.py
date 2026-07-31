#!/usr/bin/env python3
"""Evaluate a hybrid PPO checkpoint against fixed opponents and both seats."""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
from pathlib import Path

from train_hybrid_ppo import rollout_task, summarize_games


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--base-agent", type=Path, default=ROOT / "main.py")
    parser.add_argument(
        "--pulse-agent", type=Path, default=ROOT / "agents" / "pulse_breaker_v2.py"
    )
    parser.add_argument("--score800-reference", type=Path)
    parser.add_argument("--seeds", nargs="+", type=int, required=True)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    opponents = [
        {
            "name": "incumbent",
            "kind": "scripted",
            "path": str(args.base_agent.resolve()),
        },
        {
            "name": "pulse",
            "kind": "scripted",
            "path": str(args.pulse_agent.resolve()),
        },
    ]
    if args.score800_reference and args.score800_reference.exists():
        opponents.append(
            {
                "name": "score800",
                "kind": "scripted",
                "path": str(args.score800_reference.resolve()),
            }
        )
    tasks = [
        {
            "candidate_checkpoint": str(args.checkpoint.resolve()),
            "base_agent": str(args.base_agent.resolve()),
            "candidate_deterministic": True,
            "record_trajectory": False,
            "opponent": opponent,
            "seed": seed,
            "seat": seat,
            "shaping_coefficient": 0.0,
        }
        for opponent in opponents
        for seed in args.seeds
        for seat in (0, 1)
    ]
    context = mp.get_context("spawn")
    with context.Pool(max(1, min(args.workers, os.cpu_count() or args.workers))) as pool:
        games = list(pool.imap_unordered(rollout_task, tasks, chunksize=1))
    result = {
        "checkpoint": str(args.checkpoint.resolve()),
        "seeds": args.seeds,
        "summary": summarize_games(games),
        "games": [
            {key: value for key, value in game.items() if key != "trajectory"}
            for game in games
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2))
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()

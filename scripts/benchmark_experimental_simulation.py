#!/usr/bin/env python3
"""Compare stable and experimental Kaggriculture fast runners.

The script checks full-trajectory parity first, then benchmarks the same games
with freshly imported agents.  It intentionally leaves the production runner
unchanged.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import importlib.util
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))

import fast_kaggriculture as stable
import experimental_fast_kaggriculture_v3 as experimental


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fingerprint(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def play(runner, agent_path: Path, opponent_path: Path, seed: int, seat: int, verify=False):
    agents = [
        load_module(agent_path, "experimental_candidate").agent,
        load_module(opponent_path, "experimental_opponent").agent,
    ]
    if seat:
        agents.reverse()

    trace = []
    if verify:
        def wrap(agent):
            def recorded(obs):
                observation = {
                    k: obs[k]
                    for k in (
                        "step", "player", "farms", "private", "market",
                        "town", "day", "hour"
                    )
                }
                before = fingerprint(observation)
                action = agent(obs)
                trace.append((before, fingerprint(action)))
                return action
            return recorded
        agents = [wrap(agent) for agent in agents]

    gc.collect()
    start = time.perf_counter()
    final = runner.run_fast_episode(agents, seed=seed)
    elapsed = time.perf_counter() - start

    terminal = [
        {
            "status": s.status,
            "reward": s.reward,
            "observation": {
                k: v
                for k, v in s.observation.items()
                if k not in ("step", "remainingOverageTime")
            },
        }
        for s in final
    ]
    assert all(s.status == "DONE" for s in final), terminal
    return elapsed, (trace, fingerprint(terminal)), [s.reward for s in final]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", type=Path, default=ROOT / "main.py")
    parser.add_argument(
        "--models",
        nargs="+",
        default=["public_v31", "public_v35", "public_v36", "public_v37"],
    )
    parser.add_argument("--seeds", type=int, default=2)
    parser.add_argument("--seed-start", type=int, default=13_091_000)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "reports/experimental_simulation_benchmark.json",
    )
    args = parser.parse_args()

    tasks = [
        (ROOT / "test" / model / "main.py", args.seed_start + 17 * i, seat)
        for model in args.models
        for i in range(args.seeds)
        for seat in (0, 1)
    ]

    for opponent, seed, seat in tasks:
        _, expected, stable_reward = play(
            stable, args.agent, opponent, seed, seat, verify=True
        )
        _, actual, experimental_reward = play(
            experimental, args.agent, opponent, seed, seat, verify=True
        )
        assert actual == expected, (
            f"trajectory mismatch: {opponent.parent.name}, seed={seed}, seat={seat}"
        )
        assert experimental_reward == stable_reward
        print(
            f"parity OK: {opponent.parent.name} seed={seed} seat={seat}",
            flush=True,
        )

    play(stable, args.agent, *tasks[0])
    play(experimental, args.agent, *tasks[0])

    samples = {"stable": [], "experimental": []}
    variants = [("stable", stable), ("experimental", experimental)]
    for repeat in range(args.repeats):
        order = variants if repeat % 2 == 0 else list(reversed(variants))
        for opponent, seed, seat in tasks:
            expected_reward = None
            for name, runner in order:
                elapsed, _, reward = play(
                    runner, args.agent, opponent, seed, seat, verify=False
                )
                assert expected_reward is None or reward == expected_reward
                expected_reward = reward
                samples[name].append(elapsed)
        print(f"timing repeat {repeat + 1}/{args.repeats} complete", flush=True)

    result = {}
    for name, values in samples.items():
        total = sum(values)
        result[name] = {
            "games": len(values),
            "seconds": total,
            "games_per_second": len(values) / total,
            "median_seconds": statistics.median(values),
            "samples_seconds": values,
        }

    report = {
        "models": args.models,
        "seeds": args.seeds,
        "seed_start": args.seed_start,
        "repeats": args.repeats,
        "trajectory_games": len(tasks),
        "results": result,
        "speedup_experimental_vs_stable": (
            result["stable"]["seconds"] / result["experimental"]["seconds"]
        ),
        "source_sha256": {
            str(path): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (
                args.agent,
                ROOT / "training/fast_kaggriculture.py",
                ROOT / "training/experimental_fast_kaggriculture.py",
                ROOT / "training/experimental_fast_kaggriculture_v2.py",
                ROOT / "training/experimental_fast_kaggriculture_v3.py",
            )
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")

    print(json.dumps({k: v for k, v in report.items() if k != "results"}, indent=2))
    for name, stats in result.items():
        print(
            f"{name}: {stats['games_per_second']:.3f} games/s "
            f"median={stats['median_seconds']:.4f}s"
        )


if __name__ == "__main__":
    main()

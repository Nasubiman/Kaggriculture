#!/usr/bin/env python3
"""Parity-check and benchmark native acceleration of reference opponents.

The candidate is kept on the already-validated native path in both variants.
Only the loaded reference module changes, so the timing ratio isolates the cost
of accelerating evaluation opponents without modifying their source files.
"""
from __future__ import annotations

import gc
import json
import statistics
import time
from pathlib import Path

import benchmark_native_agent_runtime as base
from kaggle_environments import make

ROOT = Path(__file__).resolve().parents[1]


def play_fast(opponent: Path, seed: int, seat: int, opponent_native: bool, verify: bool):
    tag = f"{opponent.parent.name}_{opponent_native}_{seed}_{seat}"
    candidate_module = base.load_module(ROOT / "main.py", f"oppbench_candidate_{tag}", True)
    rival_module = base.load_module(opponent, f"oppbench_rival_{tag}", opponent_native)
    candidate = candidate_module.agent
    rival = rival_module.agent
    trace = []
    if verify:
        candidate = base.wrap(candidate, trace, candidate_module)
        rival = base.wrap(rival, trace, rival_module)
    agents = [candidate, rival] if seat == 0 else [rival, candidate]
    gc.collect()
    start = time.perf_counter()
    final = base.runner.run_fast_episode(agents, seed=seed)
    elapsed = time.perf_counter() - start
    state, rewards = base.terminal_fp(final)
    diagnostics = {
        "chassis": getattr(rival_module, "_NATIVE_CHASSIS_DIAGNOSTIC", None),
        "similarity": getattr(rival_module, "_NATIVE_SIMILARITY_DIAGNOSTIC", None),
    }
    return elapsed, (trace, state), rewards, diagnostics


def play_official(opponent: Path, seed: int, seat: int, opponent_native: bool):
    tag = f"official_{opponent.parent.name}_{opponent_native}_{seed}_{seat}"
    candidate_module = base.load_module(ROOT / "main.py", f"oppbench_candidate_{tag}", True)
    rival_module = base.load_module(opponent, f"oppbench_rival_{tag}", opponent_native)
    trace = []
    candidate = base.wrap(candidate_module.agent, trace, candidate_module)
    rival = base.wrap(rival_module.agent, trace, rival_module)
    agents = [candidate, rival] if seat == 0 else [rival, candidate]
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed}, debug=False)
    env.run(agents)
    final = env.steps[-1]
    state, rewards = base.terminal_fp(final)
    return (trace, state), rewards


def main() -> None:
    if not base.agent_runtime.native_acceleration_available():
        raise SystemExit("native accelerator was not imported")

    models = ["public_v31", "public_v35", "public_v36", "public_v37"]
    tasks = [(ROOT / "test" / model / "main.py", 13_096_000, seat) for model in models for seat in (0, 1)]

    # Fast-runner parity across every reference used by the native benchmark.
    for opponent, seed, seat in tasks:
        _, expected, expected_rewards, _ = play_fast(opponent, seed, seat, False, True)
        _, actual, actual_rewards, diagnostics = play_fast(opponent, seed, seat, True, True)
        if actual != expected:
            base.explain_mismatch(expected, actual, diagnostics)
            raise AssertionError(f"optimized opponent fast mismatch {opponent.parent.name} seat={seat}")
        assert actual_rewards == expected_rewards
        print(
            f"optimized opponent fast parity OK: {opponent.parent.name} seat={seat} "
            f"diagnostics={diagnostics}",
            flush=True,
        )

    # Keep an official-environment guard on the two newest/heaviest references.
    for model in ("public_v36", "public_v37"):
        opponent = ROOT / "test" / model / "main.py"
        for seat in (0, 1):
            expected = play_official(opponent, 13_096_911, seat, False)
            actual = play_official(opponent, 13_096_911, seat, True)
            assert actual == expected, f"optimized opponent official mismatch {model} seat={seat}"
            print(f"optimized opponent official parity OK: {model} seat={seat}", flush=True)

    samples = {"baseline_opponent": [], "native_opponent": []}
    timing_tasks = tasks * 2
    for repeat in range(2):
        variants = [(False, "baseline_opponent"), (True, "native_opponent")]
        if repeat % 2:
            variants.reverse()
        for opponent, seed, seat in timing_tasks:
            for opponent_native, name in variants:
                elapsed, _, _, _ = play_fast(
                    opponent, seed + repeat * 17, seat, opponent_native, False
                )
                samples[name].append(elapsed)

    result = {}
    for name, values in samples.items():
        total = sum(values)
        result[name] = {
            "games": len(values),
            "seconds": total,
            "games_per_second": len(values) / total,
            "median_seconds": statistics.median(values),
        }
    result["speedup_native_opponent"] = (
        result["baseline_opponent"]["seconds"] / result["native_opponent"]["seconds"]
    )
    out = ROOT / "reports" / "native_opponent_runtime_benchmark.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()

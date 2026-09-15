#!/usr/bin/env python3
"""Parity-check and benchmark validated native acceleration for reference opponents."""
from __future__ import annotations

import gc
import json
import statistics
import sys
import time
from pathlib import Path

import benchmark_native_agent_runtime as base
from kaggle_environments import make

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))
import reference_runtime

MODELS = tuple(reference_runtime.REFERENCE_NATIVE_POLICIES)


def load_rival(opponent: Path, name: str, accelerated: bool):
    module = base.load_module(opponent, name, accelerated)
    if accelerated:
        reference_runtime.optimize_reference_agent_module(module, opponent.parent.name)
    return module.agent


def play_fast(opponent: Path, seed: int, seat: int, opponent_native: bool, verify: bool):
    tag = f"{opponent.parent.name}_{opponent_native}_{seed}_{seat}"
    candidate = base.load_module(ROOT / "main.py", f"oppbench_candidate_{tag}", True).agent
    rival = load_rival(opponent, f"oppbench_rival_{tag}", opponent_native)
    trace = []
    agents = [candidate, rival] if seat == 0 else [rival, candidate]
    if verify:
        agents = [base.wrap(agent, trace) for agent in agents]
    gc.collect()
    start = time.perf_counter()
    final = base.runner.run_fast_episode(agents, seed=seed)
    elapsed = time.perf_counter() - start
    state, rewards = base.terminal_fp(final)
    return elapsed, (trace, state), rewards


def play_official(opponent: Path, seed: int, seat: int, opponent_native: bool):
    tag = f"official_{opponent.parent.name}_{opponent_native}_{seed}_{seat}"
    candidate = base.load_module(ROOT / "main.py", f"oppbench_candidate_{tag}", True).agent
    rival = load_rival(opponent, f"oppbench_rival_{tag}", opponent_native)
    trace = []
    agents = [candidate, rival] if seat == 0 else [rival, candidate]
    agents = [base.wrap(agent, trace) for agent in agents]
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed}, debug=False)
    env.run(agents)
    final = env.steps[-1]
    state, rewards = base.terminal_fp(final)
    return (trace, state), rewards


def main() -> None:
    if not base.agent_runtime.native_acceleration_available():
        raise SystemExit("native accelerator was not imported")

    tasks = [
        (ROOT / "test" / model / "main.py", 13_096_000, seat)
        for model in MODELS
        for seat in (0, 1)
    ]

    for opponent, seed, seat in tasks:
        _, expected, expected_rewards = play_fast(opponent, seed, seat, False, True)
        _, actual, actual_rewards = play_fast(opponent, seed, seat, True, True)
        assert actual == expected, f"native opponent fast mismatch {opponent.parent.name} seat={seat}"
        assert actual_rewards == expected_rewards
        print(f"native opponent fast parity OK: {opponent.parent.name} seat={seat}", flush=True)

    for model in (
        "public_v36",
        "public_v37",
        "public_v38_low_pressure_20260914",
        "public_v41_competitive_20260914",
        "public_v41_survival_20260914",
    ):
        opponent = ROOT / "test" / model / "main.py"
        for seat in (0, 1):
            expected = play_official(opponent, 13_096_911, seat, False)
            actual = play_official(opponent, 13_096_911, seat, True)
            assert actual == expected, f"native opponent official mismatch {model} seat={seat}"
            print(f"native opponent official parity OK: {model} seat={seat}", flush=True)

    samples = {"python_opponent": [], "native_opponent": []}
    by_model = {
        model: {"python_opponent": [], "native_opponent": []}
        for model in MODELS
    }
    for repeat in range(2):
        variants = [(False, "python_opponent"), (True, "native_opponent")]
        if repeat % 2:
            variants.reverse()
        for opponent, seed, seat in tasks:
            model = opponent.parent.name
            for use_native, name in variants:
                elapsed, _, _ = play_fast(
                    opponent, seed + repeat * 17, seat, use_native, False
                )
                samples[name].append(elapsed)
                by_model[model][name].append(elapsed)

    result = {
        "policy": {
            model: list(reference_runtime.REFERENCE_NATIVE_POLICIES[model])
            for model in MODELS
        },
        "by_model": {},
    }
    for name, values in samples.items():
        total = sum(values)
        result[name] = {
            "games": len(values),
            "seconds": total,
            "games_per_second": len(values) / total,
            "median_seconds": statistics.median(values),
        }
    result["speedup_native_opponent"] = (
        result["python_opponent"]["seconds"] / result["native_opponent"]["seconds"]
    )
    for model, variants in by_model.items():
        py_total = sum(variants["python_opponent"])
        native_total = sum(variants["native_opponent"])
        result["by_model"][model] = {
            "games_per_variant": len(variants["python_opponent"]),
            "python_seconds": py_total,
            "native_seconds": native_total,
            "speedup": py_total / native_total,
        }

    out = ROOT / "reports" / "native_opponent_runtime_benchmark.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Validate the parity-safe partial-native policy for public_v37."""
from __future__ import annotations

import gc
import json
import statistics
import time
from pathlib import Path

import benchmark_native_agent_runtime as base
from kaggle_environments import make

ROOT = Path(__file__).resolve().parents[1]
OPPONENT = ROOT / "test" / "public_v37" / "main.py"
RESTORES = ("Chassis.act", "_r51_input_control")
SEED = 13_099_000


def _unwrap_python(fn):
    seen = set()
    while callable(fn) and id(fn) not in seen:
        seen.add(id(fn))
        fallback = getattr(fn, "_python_fallback", None)
        if not callable(fallback):
            break
        fn = fallback
    return fn


def _restore(module, target: str) -> None:
    if "." in target:
        owner_name, attr = target.split(".", 1)
        owner = module.__dict__.get(owner_name)
        if owner is None:
            return
        original = _unwrap_python(getattr(owner, attr, None))
        if callable(original):
            setattr(owner, attr, original)
        return
    original = _unwrap_python(module.__dict__.get(target))
    if callable(original):
        module.__dict__[target] = original


def load_rival(name: str, partial_native: bool):
    module = base.load_module(OPPONENT, name, partial_native)
    if partial_native:
        for target in RESTORES:
            _restore(module, target)
    return module


def fast(seed: int, seat: int, partial_native: bool, verify: bool):
    tag = f"v37_{partial_native}_{seed}_{seat}"
    candidate = base.load_module(ROOT / "main.py", f"candidate_{tag}", True).agent
    rival = load_rival(f"rival_{tag}", partial_native).agent
    agents = [candidate, rival] if seat == 0 else [rival, candidate]
    trace = []
    if verify:
        agents = [base.wrap(agent, trace) for agent in agents]
    gc.collect()
    start = time.perf_counter()
    final = base.runner.run_fast_episode(agents, seed=seed)
    elapsed = time.perf_counter() - start
    state, rewards = base.terminal_fp(final)
    return elapsed, (trace, state), rewards


def official(seed: int, seat: int, partial_native: bool):
    tag = f"official_v37_{partial_native}_{seed}_{seat}"
    candidate = base.load_module(ROOT / "main.py", f"candidate_{tag}", True).agent
    rival = load_rival(f"rival_{tag}", partial_native).agent
    trace = []
    agents = [candidate, rival] if seat == 0 else [rival, candidate]
    agents = [base.wrap(agent, trace) for agent in agents]
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed}, debug=False)
    env.run(agents)
    state, rewards = base.terminal_fp(env.steps[-1])
    return (trace, state), rewards


def main() -> None:
    if not base.agent_runtime.native_acceleration_available():
        raise SystemExit("native accelerator was not imported")

    for seat in (0, 1):
        _, expected, expected_rewards = fast(SEED, seat, False, True)
        _, actual, actual_rewards = fast(SEED, seat, True, True)
        assert actual == expected, f"partial native v37 fast mismatch seat={seat}"
        assert actual_rewards == expected_rewards
        print(f"partial native v37 fast parity OK seat={seat}", flush=True)

    for seat in (0, 1):
        expected = official(SEED + 911, seat, False)
        actual = official(SEED + 911, seat, True)
        assert actual == expected, f"partial native v37 official mismatch seat={seat}"
        print(f"partial native v37 official parity OK seat={seat}", flush=True)

    samples = {"python_opponent": [], "partial_native_opponent": []}
    for repeat in range(3):
        variants = [(False, "python_opponent"), (True, "partial_native_opponent")]
        if repeat & 1:
            variants.reverse()
        for seat in (0, 1):
            for partial_native, name in variants:
                elapsed, _, _ = fast(SEED + repeat * 17, seat, partial_native, False)
                samples[name].append(elapsed)

    result = {"restores": list(RESTORES)}
    for name, values in samples.items():
        total = sum(values)
        result[name] = {
            "games": len(values),
            "seconds": total,
            "games_per_second": len(values) / total,
            "median_seconds": statistics.median(values),
        }
    result["speedup"] = (
        result["python_opponent"]["seconds"]
        / result["partial_native_opponent"]["seconds"]
    )
    out = ROOT / "reports" / "native_v37_partial.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()

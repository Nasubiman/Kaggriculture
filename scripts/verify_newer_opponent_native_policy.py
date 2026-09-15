#!/usr/bin/env python3
"""Validate and benchmark native policies for newer fixed reference opponents."""
from __future__ import annotations

import gc
import json
import statistics
import time
from pathlib import Path

import benchmark_native_agent_runtime as base
from kaggle_environments import make

ROOT = Path(__file__).resolve().parents[1]
POLICIES = {
    "public_v38_low_pressure_20260914": ("_r36_reserve",),
    "public_v41_competitive_20260914": ("_r36_reserve",),
    "public_v41_survival_20260914": (),
}
SEEDS = (13_096_000, 13_097_000, 13_098_000)


def _unwrap(fn):
    seen = set()
    while callable(fn) and id(fn) not in seen:
        seen.add(id(fn))
        fallback = getattr(fn, "_python_fallback", None)
        if not callable(fallback):
            break
        fn = fallback
    return fn


def restore(module, target: str) -> None:
    if "." in target:
        owner_name, attr = target.split(".", 1)
        owner = module.__dict__.get(owner_name)
        if owner is None:
            return
        original = _unwrap(getattr(owner, attr, None))
        if callable(original):
            setattr(owner, attr, original)
        return
    original = _unwrap(module.__dict__.get(target))
    if callable(original):
        module.__dict__[target] = original


def load(path: Path, name: str, accelerated: bool):
    module = base.load_module(path, name, accelerated)
    if accelerated:
        for target in POLICIES[path.parent.name]:
            restore(module, target)
    return module


def play_fast(opponent: Path, seed: int, seat: int, accelerated: bool, verify: bool):
    tag = f"newpolicy_{opponent.parent.name}_{accelerated}_{seed}_{seat}"
    candidate = base.load_module(ROOT / "main.py", f"candidate_{tag}", True).agent
    rival = load(opponent, f"rival_{tag}", accelerated).agent
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


def play_official(opponent: Path, seed: int, seat: int, accelerated: bool):
    tag = f"newpolicy_official_{opponent.parent.name}_{accelerated}_{seed}_{seat}"
    candidate = base.load_module(ROOT / "main.py", f"candidate_{tag}", True).agent
    rival = load(opponent, f"rival_{tag}", accelerated).agent
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

    for model in POLICIES:
        opponent = ROOT / "test" / model / "main.py"
        for seed in SEEDS:
            for seat in (0, 1):
                _, expected, expected_rewards = play_fast(opponent, seed, seat, False, True)
                _, actual, actual_rewards = play_fast(opponent, seed, seat, True, True)
                assert actual == expected, f"fast mismatch {model} seed={seed} seat={seat}"
                assert actual_rewards == expected_rewards
                print(f"fast parity OK: {model} seed={seed} seat={seat}", flush=True)

    official_seed = 13_099_911
    for model in POLICIES:
        opponent = ROOT / "test" / model / "main.py"
        for seat in (0, 1):
            expected = play_official(opponent, official_seed, seat, False)
            actual = play_official(opponent, official_seed, seat, True)
            assert actual == expected, f"official mismatch {model} seat={seat}"
            print(f"official parity OK: {model} seat={seat}", flush=True)

    by_model = {}
    all_python = []
    all_native = []
    for model in POLICIES:
        opponent = ROOT / "test" / model / "main.py"
        py_samples = []
        native_samples = []
        for repeat in range(2):
            variants = [(False, py_samples), (True, native_samples)]
            if repeat % 2:
                variants.reverse()
            for seat in (0, 1):
                for accelerated, bucket in variants:
                    elapsed, _, _ = play_fast(opponent, 13_100_000 + repeat * 17, seat, accelerated, False)
                    bucket.append(elapsed)
        py_total = sum(py_samples)
        native_total = sum(native_samples)
        all_python.extend(py_samples)
        all_native.extend(native_samples)
        by_model[model] = {
            "restores": list(POLICIES[model]),
            "games_per_variant": len(py_samples),
            "python_seconds": py_total,
            "native_seconds": native_total,
            "speedup": py_total / native_total,
            "python_median_seconds": statistics.median(py_samples),
            "native_median_seconds": statistics.median(native_samples),
        }

    result = {
        "policies": {k: list(v) for k, v in POLICIES.items()},
        "parity_fast_seeds": list(SEEDS),
        "parity_official_seed": official_seed,
        "by_model": by_model,
        "overall": {
            "games_per_variant": len(all_python),
            "python_seconds": sum(all_python),
            "native_seconds": sum(all_native),
            "speedup": sum(all_python) / sum(all_native),
            "python_median_seconds": statistics.median(all_python),
            "native_median_seconds": statistics.median(all_native),
        },
    }
    out = ROOT / "reports" / "newer_opponent_native_policy.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()

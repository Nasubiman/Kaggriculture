#!/usr/bin/env python3
"""Parity-check and benchmark optional C++ agent runtime acceleration."""
from __future__ import annotations

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

import agent_runtime
import experimental_fast_kaggriculture_v3 as runner
from kaggle_environments import make


def load_module(path: Path, name: str, use_native: bool):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    saved = agent_runtime._native
    try:
        if not use_native:
            agent_runtime._native = None
        agent_runtime.optimize_agent_module(module)
    finally:
        agent_runtime._native = saved
    return module


def fp(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def wrap(agent, trace):
    def recorded(obs):
        observation = {k: obs[k] for k in (
            "step", "player", "farms", "private", "market", "town", "day", "hour"
        )}
        before = fp(observation)
        action = agent(obs)
        trace.append((before, fp(action)))
        return action
    return recorded


def terminal_fp(final):
    terminal = [
        {
            "status": str(s.status),
            "reward": s.reward,
            "observation": {
                k: v for k, v in s.observation.items()
                if k not in ("step", "remainingOverageTime")
            },
        }
        for s in final
    ]
    return fp(terminal), [float(s.reward) for s in final]


def play_fast(opponent: Path, seed: int, seat: int, use_native: bool, verify: bool):
    candidate = load_module(ROOT / "main.py", f"candidate_{use_native}_{seed}_{seat}", use_native).agent
    rival = load_module(opponent, f"opponent_{use_native}_{seed}_{seat}", False).agent
    agents = [candidate, rival] if seat == 0 else [rival, candidate]
    trace = []
    if verify:
        agents = [wrap(a, trace) for a in agents]
    gc.collect()
    start = time.perf_counter()
    final = runner.run_fast_episode(agents, seed=seed)
    elapsed = time.perf_counter() - start
    state, rewards = terminal_fp(final)
    return elapsed, (trace, state), rewards


def play_official(opponent: Path, seed: int, seat: int, use_native: bool):
    candidate = load_module(ROOT / "main.py", f"official_candidate_{use_native}_{seed}_{seat}", use_native).agent
    rival = load_module(opponent, f"official_opponent_{use_native}_{seed}_{seat}", False).agent
    agents = [candidate, rival] if seat == 0 else [rival, candidate]
    trace = []
    agents = [wrap(a, trace) for a in agents]
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed}, debug=False)
    env.run(agents)
    final = env.steps[-1]
    state, rewards = terminal_fp(final)
    return trace, state, rewards


def main():
    if not agent_runtime.native_acceleration_available():
        raise SystemExit("native accelerator was not imported")

    models = ["public_v31", "public_v35", "public_v36", "public_v37"]
    tasks = [(ROOT / "test" / m / "main.py", 13_094_000, seat) for m in models for seat in (0, 1)]

    for opponent, seed, seat in tasks:
        _, expected, expected_rewards = play_fast(opponent, seed, seat, False, True)
        _, actual, actual_rewards = play_fast(opponent, seed, seat, True, True)
        assert actual == expected, f"native fast mismatch {opponent.parent.name} seat={seat}"
        assert actual_rewards == expected_rewards
        print(f"native fast parity OK: {opponent.parent.name} seat={seat}", flush=True)

    for model in ("public_v36", "public_v37"):
        opponent = ROOT / "test" / model / "main.py"
        for seat in (0, 1):
            expected = play_official(opponent, 13_094_911, seat, False)
            actual = play_official(opponent, 13_094_911, seat, True)
            assert actual == expected, f"native official mismatch {model} seat={seat}"
            print(f"native official parity OK: {model} seat={seat}", flush=True)

    samples = {"python": [], "native": []}
    timing_tasks = tasks * 2
    for repeat in range(2):
        variants = [(False, "python"), (True, "native")]
        if repeat % 2:
            variants.reverse()
        for opponent, seed, seat in timing_tasks:
            for use_native, name in variants:
                elapsed, _, _ = play_fast(opponent, seed + repeat * 17, seat, use_native, False)
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
    result["speedup_native_vs_python"] = result["python"]["seconds"] / result["native"]["seconds"]
    out = ROOT / "reports" / "native_agent_runtime_benchmark.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()

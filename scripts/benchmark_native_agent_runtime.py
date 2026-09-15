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

_NATIVE_SLOTS = ("_native", "_reserve_native", "_controller_native", "_chassis_native", "_budget_native")


def load_module(path: Path, name: str, use_native: bool):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    saved = {slot: getattr(agent_runtime, slot, None) for slot in _NATIVE_SLOTS}
    try:
        if not use_native:
            for slot in _NATIVE_SLOTS:
                setattr(agent_runtime, slot, None)
        agent_runtime.optimize_agent_module(module)
    finally:
        for slot, value in saved.items():
            setattr(agent_runtime, slot, value)
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
        trace.append({
            "step": int(obs["step"]),
            "player": int(obs["player"]),
            "before": before,
            "action_fp": fp(action),
            "action": json.dumps(action, sort_keys=True, separators=(",", ":")),
        })
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
    candidate_module = load_module(ROOT / "main.py", f"candidate_{use_native}_{seed}_{seat}", use_native)
    candidate = candidate_module.agent
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
    diagnostics = {
        "chassis": getattr(candidate_module, "_NATIVE_CHASSIS_DIAGNOSTIC", None),
        "similarity": getattr(candidate_module, "_NATIVE_SIMILARITY_DIAGNOSTIC", None),
    }
    return elapsed, (trace, state), rewards, diagnostics


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


def explain_mismatch(expected, actual, diagnostics):
    etrace, estate = expected
    atrace, astate = actual
    limit = min(len(etrace), len(atrace))
    for i in range(limit):
        if etrace[i] != atrace[i]:
            print("FIRST_NATIVE_DIVERGENCE", json.dumps({
                "trace_index": i,
                "expected": etrace[i],
                "actual": atrace[i],
                "diagnostics": diagnostics,
            }, sort_keys=True), flush=True)
            return
    if len(etrace) != len(atrace):
        print("FIRST_NATIVE_DIVERGENCE", json.dumps({
            "trace_length_expected": len(etrace),
            "trace_length_actual": len(atrace),
            "diagnostics": diagnostics,
        }, sort_keys=True), flush=True)
        return
    print("FIRST_NATIVE_DIVERGENCE", json.dumps({
        "terminal_expected": estate,
        "terminal_actual": astate,
        "diagnostics": diagnostics,
    }, sort_keys=True), flush=True)


def main():
    if not agent_runtime.native_acceleration_available():
        raise SystemExit("native accelerator was not imported")

    models = ["public_v31", "public_v35", "public_v36", "public_v37"]
    tasks = [(ROOT / "test" / m / "main.py", 13_094_000, seat) for m in models for seat in (0, 1)]

    for opponent, seed, seat in tasks:
        _, expected, expected_rewards, _ = play_fast(opponent, seed, seat, False, True)
        _, actual, actual_rewards, diagnostics = play_fast(opponent, seed, seat, True, True)
        if actual != expected:
            explain_mismatch(expected, actual, diagnostics)
            raise AssertionError(f"native fast mismatch {opponent.parent.name} seat={seat}")
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
                elapsed, _, _, _ = play_fast(opponent, seed + repeat * 17, seat, use_native, False)
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

#!/usr/bin/env python3
"""Verify and benchmark the semantics-preserving main.py speed patch.

Requires scripts/apply_main_speed_patch.py to have run first.  Checks full
agent-action/observation traces against the saved pre-patch main both through
the experimental fast simulator and through kaggle-environments itself.
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

import experimental_fast_kaggriculture_v3 as fastsim

BASE = ROOT / "training/reference_main_pre_main_speed.py"
PATCHED = ROOT / "main.py"


def load_agent(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.agent


def fp(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def public_obs(obs):
    return {
        key: obs[key]
        for key in ("step", "player", "farms", "private", "market", "town", "day", "hour")
        if key in obs
    }


def wrapped(agent, trace, actor):
    def call(obs, configuration=None):
        before = fp(public_obs(obs))
        try:
            action = agent(obs, configuration)
        except TypeError:
            action = agent(obs)
        trace.append((actor, before, fp(action)))
        return action
    return call


def play_fast(candidate_path: Path, opponent_path: Path, seed: int, seat: int, verify: bool):
    candidate = load_agent(candidate_path, f"main_speed_candidate_{candidate_path.stem}_{seed}_{seat}_{time.time_ns()}")
    opponent = load_agent(opponent_path, f"main_speed_opponent_{seed}_{seat}_{time.time_ns()}")
    trace = []
    agents = [candidate, opponent] if seat == 0 else [opponent, candidate]
    if verify:
        agents = [wrapped(agent, trace, actor) for actor, agent in enumerate(agents)]
    gc.collect()
    t0 = time.perf_counter()
    final = fastsim.run_fast_episode(agents, seed=seed)
    elapsed = time.perf_counter() - t0
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
    assert all(str(s.status) == "DONE" for s in final), terminal
    return elapsed, (trace, fp(terminal)), [s.reward for s in final]


def play_official(candidate_path: Path, opponent_path: Path, seed: int, seat: int):
    from kaggle_environments import make

    candidate = load_agent(candidate_path, f"official_candidate_{candidate_path.stem}_{seed}_{seat}_{time.time_ns()}")
    opponent = load_agent(opponent_path, f"official_opponent_{seed}_{seat}_{time.time_ns()}")
    trace = []
    raw = [candidate, opponent] if seat == 0 else [opponent, candidate]
    agents = [wrapped(agent, trace, actor) for actor, agent in enumerate(raw)]
    env = make(
        "kaggriculture",
        configuration={"episodeSteps": 720, "seed": seed},
        debug=False,
    )
    env.run(agents)
    final = env.steps[-1]
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
    assert all(str(s.status) == "DONE" for s in final), terminal
    return trace, fp(terminal), [s.reward for s in final]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=1)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--seed-start", type=int, default=13_092_000)
    parser.add_argument(
        "--models", nargs="+",
        default=["public_v31", "public_v35", "public_v36", "public_v37"],
    )
    parser.add_argument(
        "--official-models", nargs="+", default=["public_v36", "public_v37"]
    )
    parser.add_argument(
        "--output", type=Path,
        default=ROOT / "reports/main_speed_benchmark.json",
    )
    args = parser.parse_args()

    if not BASE.exists():
        raise SystemExit(f"missing baseline {BASE}; run apply_main_speed_patch.py first")
    if "MAIN_SPEED_PATCH_20260914_V1" not in PATCHED.read_text():
        raise SystemExit("main.py speed patch is not applied")

    fast_tasks = [
        (ROOT / "test" / model / "main.py", args.seed_start + 17 * i, seat)
        for model in args.models for i in range(args.seeds) for seat in (0, 1)
    ]

    for opponent, seed, seat in fast_tasks:
        _, expected, expected_reward = play_fast(BASE, opponent, seed, seat, True)
        _, actual, actual_reward = play_fast(PATCHED, opponent, seed, seat, True)
        assert actual == expected, (
            f"fast trajectory mismatch: {opponent.parent.name} seed={seed} seat={seat}"
        )
        assert actual_reward == expected_reward
        print(f"fast main parity OK: {opponent.parent.name} seed={seed} seat={seat}", flush=True)

    official_tasks = [
        (ROOT / "test" / model / "main.py", args.seed_start + 911, seat)
        for model in args.official_models for seat in (0, 1)
    ]
    for opponent, seed, seat in official_tasks:
        expected = play_official(BASE, opponent, seed, seat)
        actual = play_official(PATCHED, opponent, seed, seat)
        assert actual == expected, (
            f"OFFICIAL trajectory mismatch: {opponent.parent.name} seed={seed} seat={seat}"
        )
        print(f"official main parity OK: {opponent.parent.name} seed={seed} seat={seat}", flush=True)

    # Warm once before timing.
    play_fast(BASE, *fast_tasks[0], False)
    play_fast(PATCHED, *fast_tasks[0], False)

    samples = {"baseline_main": [], "patched_main": []}
    variants = [("baseline_main", BASE), ("patched_main", PATCHED)]
    for repeat in range(args.repeats):
        order = variants if repeat % 2 == 0 else list(reversed(variants))
        for opponent, seed, seat in fast_tasks:
            expected_reward = None
            for name, path in order:
                elapsed, _, reward = play_fast(path, opponent, seed, seat, False)
                assert expected_reward is None or reward == expected_reward
                expected_reward = reward
                samples[name].append(elapsed)
        print(f"main timing repeat {repeat + 1}/{args.repeats} complete", flush=True)

    results = {}
    for name, values in samples.items():
        total = sum(values)
        results[name] = {
            "games": len(values),
            "seconds": total,
            "games_per_second": len(values) / total,
            "median_seconds": statistics.median(values),
            "samples_seconds": values,
        }
    report = {
        "fast_trajectory_games": len(fast_tasks),
        "official_trajectory_games": len(official_tasks),
        "results": results,
        "speedup_patched_vs_baseline": (
            results["baseline_main"]["seconds"] / results["patched_main"]["seconds"]
        ),
        "baseline_sha256": hashlib.sha256(BASE.read_bytes()).hexdigest(),
        "patched_sha256": hashlib.sha256(PATCHED.read_bytes()).hexdigest(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

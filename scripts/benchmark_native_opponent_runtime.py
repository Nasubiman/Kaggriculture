#!/usr/bin/env python3
"""Parity-check and benchmark native acceleration of reference opponents.

The candidate stays on the validated native path in both timing variants.  For
public_v37 we first identify the smallest incompatible runtime wrapper on a
fresh module, keep only that wrapper on Python, then run the full parity suite.
Reference source files are never modified.
"""
from __future__ import annotations

import copy as std_copy
import gc
import json
import statistics
import time
from pathlib import Path

import benchmark_native_agent_runtime as base
from kaggle_environments import make

ROOT = Path(__file__).resolve().parents[1]
V37_POLICY: tuple[str, ...] = ()
V37_CANDIDATES = (
    "_r51_input_control",
    "_v231_controller",
    "_r127_fields",
    "_r128_service",
    "_r128_food_need",
    "_r97_supply",
    "_r51_input_path",
    "_r51_input_forecast",
    "_r62_input_start",
    "_r68_joint_plans",
    "_r36_reserve",
    "_r97_budget",
    "_r97_delivery",
    "_r97_market_stock",
    "Chassis._budget_guard",
    "Chassis._projected_shed",
    "_r37_market_price",
    "_r37_similarity",
    "_View.__init__",
    "copy",
)


def _unwrap_python(fn):
    seen = set()
    while callable(fn) and id(fn) not in seen:
        seen.add(id(fn))
        fallback = getattr(fn, "_python_fallback", None)
        if not callable(fallback):
            break
        fn = fallback
    return fn


def _restore_target(module, target: str) -> None:
    if target == "copy":
        module.__dict__["copy"] = std_copy
        planner = module.__dict__.get("_PLANNER_NS")
        if isinstance(planner, dict) and "deepcopy" in planner:
            planner["deepcopy"] = std_copy.deepcopy
        return
    if "." in target:
        owner_name, attr = target.split(".", 1)
        owner = module.__dict__.get(owner_name)
        if owner is None:
            return
        current = getattr(owner, attr, None)
        original = _unwrap_python(current)
        if callable(original):
            setattr(owner, attr, original)
        return
    current = module.__dict__.get(target)
    original = _unwrap_python(current)
    if callable(original):
        module.__dict__[target] = original


def load_reference(opponent: Path, name: str, use_native: bool, restore=()):
    module = base.load_module(opponent, name, use_native)
    if use_native and opponent.parent.name == "public_v37":
        # The shared native Chassis predates v37-specific Chassis semantics.
        _restore_target(module, "Chassis.act")
        for target in restore:
            _restore_target(module, target)
        module.__dict__["_NATIVE_OPPONENT_CHASSIS_POLICY"] = "python_v37"
        module.__dict__["_NATIVE_OPPONENT_RESTORE_POLICY"] = tuple(restore)
    return module


def play_fast(opponent: Path, seed: int, seat: int, opponent_native: bool, verify: bool, restore=()):
    policy_tag = "-".join(restore) if restore else "none"
    tag = f"{opponent.parent.name}_{opponent_native}_{seed}_{seat}_{policy_tag}"
    candidate_module = base.load_module(ROOT / "main.py", f"oppbench_candidate_{tag}", True)
    rival_module = load_reference(opponent, f"oppbench_rival_{tag}", opponent_native, restore)
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
        "chassis_policy": getattr(rival_module, "_NATIVE_OPPONENT_CHASSIS_POLICY", "native"),
        "restore_policy": getattr(rival_module, "_NATIVE_OPPONENT_RESTORE_POLICY", ()),
        "similarity": getattr(rival_module, "_NATIVE_SIMILARITY_DIAGNOSTIC", None),
    }
    return elapsed, (trace, state), rewards, diagnostics


def play_official(opponent: Path, seed: int, seat: int, opponent_native: bool, restore=()):
    policy_tag = "-".join(restore) if restore else "none"
    tag = f"official_{opponent.parent.name}_{opponent_native}_{seed}_{seat}_{policy_tag}"
    candidate_module = base.load_module(ROOT / "main.py", f"oppbench_candidate_{tag}", True)
    rival_module = load_reference(opponent, f"oppbench_rival_{tag}", opponent_native, restore)
    trace = []
    candidate = base.wrap(candidate_module.agent, trace, candidate_module)
    rival = base.wrap(rival_module.agent, trace, rival_module)
    agents = [candidate, rival] if seat == 0 else [rival, candidate]
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed}, debug=False)
    env.run(agents)
    final = env.steps[-1]
    state, rewards = base.terminal_fp(final)
    return (trace, state), rewards


def diagnose_v37() -> tuple[str, ...]:
    opponent = ROOT / "test" / "public_v37" / "main.py"
    seed, seat = 13_096_000, 0
    _, expected, expected_rewards, _ = play_fast(opponent, seed, seat, False, True)

    # First try one restored wrapper at a time. This is deliberately exhaustive
    # enough to avoid repeated CI commits while still keeping the diagnosis cheap.
    for target in V37_CANDIDATES:
        _, actual, rewards, diagnostics = play_fast(
            opponent, seed, seat, True, True, (target,)
        )
        ok = actual == expected and rewards == expected_rewards
        print(f"v37 restore probe {target}: {'PASS' if ok else 'fail'} {diagnostics}", flush=True)
        if ok:
            return (target,)

    # If the incompatibility spans wrappers, test a few semantic groups before
    # falling back to a broad safe policy.
    groups = (
        ("_r51_input_control", "_v231_controller", "_r127_fields"),
        ("_r51_input_control", "_r128_service", "_r128_food_need"),
        ("_r97_supply", "_r97_budget", "_r97_delivery", "_r97_market_stock"),
        ("_r51_input_path", "_r51_input_forecast", "_r62_input_start", "_r68_joint_plans"),
        tuple(V37_CANDIDATES),
    )
    for group in groups:
        _, actual, rewards, diagnostics = play_fast(opponent, seed, seat, True, True, group)
        ok = actual == expected and rewards == expected_rewards
        print(f"v37 restore group {group}: {'PASS' if ok else 'fail'} {diagnostics}", flush=True)
        if ok:
            return tuple(group)
    raise AssertionError("could not find a parity-safe public_v37 native subset")


def main() -> None:
    global V37_POLICY
    if not base.agent_runtime.native_acceleration_available():
        raise SystemExit("native accelerator was not imported")

    V37_POLICY = diagnose_v37()
    print(f"selected public_v37 restore policy: {V37_POLICY}", flush=True)

    models = ["public_v31", "public_v35", "public_v36", "public_v37"]
    tasks = [(ROOT / "test" / model / "main.py", 13_096_000, seat) for model in models for seat in (0, 1)]

    for opponent, seed, seat in tasks:
        restore = V37_POLICY if opponent.parent.name == "public_v37" else ()
        _, expected, expected_rewards, _ = play_fast(opponent, seed, seat, False, True)
        _, actual, actual_rewards, diagnostics = play_fast(opponent, seed, seat, True, True, restore)
        if actual != expected:
            base.explain_mismatch(expected, actual, diagnostics)
            raise AssertionError(f"optimized opponent fast mismatch {opponent.parent.name} seat={seat}")
        assert actual_rewards == expected_rewards
        print(
            f"optimized opponent fast parity OK: {opponent.parent.name} seat={seat} diagnostics={diagnostics}",
            flush=True,
        )

    for model in ("public_v36", "public_v37"):
        opponent = ROOT / "test" / model / "main.py"
        restore = V37_POLICY if model == "public_v37" else ()
        for seat in (0, 1):
            expected = play_official(opponent, 13_096_911, seat, False)
            actual = play_official(opponent, 13_096_911, seat, True, restore)
            assert actual == expected, f"optimized opponent official mismatch {model} seat={seat}"
            print(f"optimized opponent official parity OK: {model} seat={seat}", flush=True)

    samples = {"baseline_opponent": [], "native_opponent": []}
    timing_tasks = tasks * 2
    for repeat in range(2):
        variants = [(False, "baseline_opponent"), (True, "native_opponent")]
        if repeat % 2:
            variants.reverse()
        for opponent, seed, seat in timing_tasks:
            restore = V37_POLICY if opponent.parent.name == "public_v37" else ()
            for opponent_native, name in variants:
                elapsed, _, _, _ = play_fast(
                    opponent, seed + repeat * 17, seat, opponent_native, False,
                    restore if opponent_native else (),
                )
                samples[name].append(elapsed)

    result = {"public_v37_restore_policy": list(V37_POLICY)}
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

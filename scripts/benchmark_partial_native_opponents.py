#!/usr/bin/env python3
"""Find a parity-safe partial-native policy for v37+ reference opponents."""
from __future__ import annotations

import json
import statistics
import time
from pathlib import Path

import benchmark_native_agent_runtime as base

ROOT = Path(__file__).resolve().parents[1]
MODELS = (
    "public_v37",
    "public_v38_low_pressure_20260914",
    "public_v41_competitive_20260914",
    "public_v41_survival_20260914",
)
POLICIES = (
    ("python_chassis", ("Chassis.act",)),
    ("python_chassis_input", ("Chassis.act", "_r51_input_control")),
)
SEED = 13_098_000


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
        current = getattr(owner, attr, None)
        original = _unwrap_python(current)
        if callable(original):
            setattr(owner, attr, original)
        return
    current = module.__dict__.get(target)
    original = _unwrap_python(current)
    if callable(original):
        module.__dict__[target] = original


def load_rival(path: Path, name: str, native: bool, restores=()):
    module = base.load_module(path, name, native)
    if native:
        for target in restores:
            _restore(module, target)
    return module


def play(opponent: Path, seed: int, seat: int, native: bool, restores=(), verify=False):
    tag = f"partial_{opponent.parent.name}_{native}_{seed}_{seat}_{len(restores)}"
    candidate = base.load_module(ROOT / "main.py", f"candidate_{tag}", True).agent
    rival = load_rival(opponent, f"rival_{tag}", native, restores).agent
    agents = [candidate, rival] if seat == 0 else [rival, candidate]
    trace = []
    if verify:
        agents = [base.wrap(agent, trace) for agent in agents]
    start = time.perf_counter()
    final = base.runner.run_fast_episode(agents, seed=seed)
    elapsed = time.perf_counter() - start
    state, rewards = base.terminal_fp(final)
    return elapsed, (trace, state), rewards


def policy_parity(opponent: Path, restores) -> bool:
    for seat in (0, 1):
        _, expected, expected_rewards = play(opponent, SEED, seat, False, verify=True)
        _, actual, actual_rewards = play(opponent, SEED, seat, True, restores, verify=True)
        if actual != expected or actual_rewards != expected_rewards:
            return False
    return True


def benchmark(opponent: Path, restores):
    samples = {"python": [], "partial_native": []}
    for repeat in range(2):
        variants = [(False, "python"), (True, "partial_native")]
        if repeat & 1:
            variants.reverse()
        for seat in (0, 1):
            for native, name in variants:
                elapsed, _, _ = play(
                    opponent,
                    SEED + repeat * 17,
                    seat,
                    native,
                    restores if native else (),
                    False,
                )
                samples[name].append(elapsed)
    py_total = sum(samples["python"])
    native_total = sum(samples["partial_native"])
    return {
        "games_per_variant": len(samples["python"]),
        "python_seconds": py_total,
        "partial_native_seconds": native_total,
        "python_median": statistics.median(samples["python"]),
        "partial_native_median": statistics.median(samples["partial_native"]),
        "speedup": py_total / native_total,
    }


def main() -> None:
    if not base.agent_runtime.native_acceleration_available():
        raise SystemExit("native accelerator was not imported")
    result = {"models": {}}
    for model in MODELS:
        opponent = ROOT / "test" / model / "main.py"
        selected = None
        probes = {}
        for policy_name, restores in POLICIES:
            ok = policy_parity(opponent, restores)
            probes[policy_name] = ok
            print(f"partial native parity {model} {policy_name}: {'OK' if ok else 'MISMATCH'}", flush=True)
            if ok:
                selected = (policy_name, restores)
                break
        entry = {"probes": probes, "selected_policy": selected[0] if selected else None}
        if selected:
            entry["restores"] = list(selected[1])
            entry["benchmark"] = benchmark(opponent, selected[1])
        result["models"][model] = entry
    out = ROOT / "reports" / "partial_native_opponents.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Find a seed-robust partial-native policy for v38/v41 reference agents."""
from __future__ import annotations

import json
from pathlib import Path

import benchmark_native_agent_runtime as base

ROOT = Path(__file__).resolve().parents[1]
MODELS = (
    "public_v38_low_pressure_20260914",
    "public_v41_competitive_20260914",
    "public_v41_survival_20260914",
)
SEEDS = (13_096_000, 13_097_000, 13_098_000)
POLICIES = (
    ("full_native", ()),
    ("python_chassis", ("Chassis.act",)),
    ("python_input", ("_r51_input_control",)),
    ("python_chassis_input", ("Chassis.act", "_r51_input_control")),
    ("python_chassis_input_controller", ("Chassis.act", "_r51_input_control", "_v231_controller")),
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


def load_rival(path: Path, name: str, native: bool, restores=()):
    module = base.load_module(path, name, native)
    if native:
        for target in restores:
            _restore(module, target)
    return module


def play(opponent: Path, seed: int, seat: int, native: bool, restores=()):
    tag = f"newpolicy_{opponent.parent.name}_{native}_{seed}_{seat}_{len(restores)}"
    candidate = base.load_module(ROOT / "main.py", f"candidate_{tag}", True).agent
    rival = load_rival(opponent, f"rival_{tag}", native, restores).agent
    trace = []
    agents = [candidate, rival] if seat == 0 else [rival, candidate]
    agents = [base.wrap(agent, trace) for agent in agents]
    final = base.runner.run_fast_episode(agents, seed=seed)
    state, rewards = base.terminal_fp(final)
    return (trace, state), rewards


def main() -> None:
    result = {"models": {}}
    for model in MODELS:
        opponent = ROOT / "test" / model / "main.py"
        model_result = {"policies": {}}
        selected = None
        baselines = {}
        for seed in SEEDS:
            for seat in (0, 1):
                baselines[(seed, seat)] = play(opponent, seed, seat, False)
        for policy_name, restores in POLICIES:
            failures = []
            for seed in SEEDS:
                for seat in (0, 1):
                    actual = play(opponent, seed, seat, True, restores)
                    if actual != baselines[(seed, seat)]:
                        failures.append({"seed": seed, "seat": seat})
            ok = not failures
            model_result["policies"][policy_name] = {
                "restores": list(restores),
                "ok": ok,
                "failures": failures,
            }
            print(f"{model} {policy_name}: {'OK' if ok else failures}", flush=True)
            if ok and selected is None:
                selected = policy_name
        model_result["selected_policy"] = selected
        result["models"][model] = model_result

    out = ROOT / "reports" / "newer_native_policy.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()

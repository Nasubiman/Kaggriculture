#!/usr/bin/env python3
"""Locate the smallest native wrapper restore set for v38/v41 competitive."""
from __future__ import annotations

import copy as std_copy
import json
from pathlib import Path

import benchmark_native_agent_runtime as base

ROOT = Path(__file__).resolve().parents[1]
MODELS = (
    "public_v38_low_pressure_20260914",
    "public_v41_competitive_20260914",
)
SEED = 13_096_000
SINGLES = (
    "Chassis.act",
    "_r51_input_control",
    "_v231_controller",
    "_r127_fields",
    "_r128_service",
    "_r128_food_need",
    "_r97_budget",
    "_r97_delivery",
    "_r97_market_stock",
    "_r37_quote_priority",
    "_r36_reserve",
    "_r51_input_path",
    "_r51_input_forecast",
    "_r62_input_start",
    "_r68_joint_plans",
    "Chassis._budget_guard",
    "Chassis._projected_shed",
    "_r37_market_price",
    "_r37_similarity",
    "_View.__init__",
    "_r51_input_gain",
    "copy",
)
GROUPS = (
    ("service", ("_r127_fields", "_r128_service", "_r128_food_need")),
    ("sales", ("_r97_budget", "_r97_delivery", "_r97_market_stock", "_r37_quote_priority")),
    ("planning", ("_r51_input_control", "_v231_controller", "_r51_input_path", "_r51_input_forecast", "_r62_input_start", "_r68_joint_plans")),
    ("chassis", ("Chassis.act", "Chassis._budget_guard", "Chassis._projected_shed", "_View.__init__")),
    ("market_similarity_reserve", ("_r37_market_price", "_r37_similarity", "_r36_reserve")),
    ("copy_gain", ("copy", "_r51_input_gain")),
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
    if target == "copy":
        module.__dict__["copy"] = std_copy
        planner = module.__dict__.get("_PLANNER_NS")
        if isinstance(planner, dict):
            planner["deepcopy"] = std_copy.deepcopy
        return
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


def load_rival(path: Path, name: str, restores=()):
    module = base.load_module(path, name, True)
    for target in restores:
        _restore(module, target)
    return module


def play(opponent: Path, seat: int, native: bool, restores=()):
    tag = f"wrapdiag_{opponent.parent.name}_{seat}_{native}_{abs(hash(restores))}"
    candidate = base.load_module(ROOT / "main.py", f"candidate_{tag}", True).agent
    if native:
        rival = load_rival(opponent, f"rival_{tag}", restores).agent
    else:
        rival = base.load_module(opponent, f"rival_{tag}", False).agent
    trace = []
    agents = [candidate, rival] if seat == 0 else [rival, candidate]
    agents = [base.wrap(agent, trace) for agent in agents]
    final = base.runner.run_fast_episode(agents, seed=SEED)
    state, rewards = base.terminal_fp(final)
    return trace, state, rewards


def parity(opponent: Path, baselines, restores) -> tuple[bool, list[int]]:
    failures = []
    for seat in (0, 1):
        actual = play(opponent, seat, True, restores)
        if actual != baselines[seat]:
            failures.append(seat)
            # Seat 0 already reproduces both current failures; do not skip seat 1
            # because a future policy must be symmetric and exact.
    return not failures, failures


def main() -> None:
    result = {"seed": SEED, "models": {}}
    for model in MODELS:
        opponent = ROOT / "test" / model / "main.py"
        baselines = {seat: play(opponent, seat, False) for seat in (0, 1)}
        entry = {"single_restores": {}, "group_restores": {}, "selected": None}

        for target in SINGLES:
            ok, failures = parity(opponent, baselines, (target,))
            entry["single_restores"][target] = {"ok": ok, "failures": failures}
            print(f"{model} single {target}: {'OK' if ok else failures}", flush=True)
            if ok and entry["selected"] is None:
                entry["selected"] = [target]

        if entry["selected"] is None:
            for group_name, restores in GROUPS:
                ok, failures = parity(opponent, baselines, restores)
                entry["group_restores"][group_name] = {
                    "restores": list(restores),
                    "ok": ok,
                    "failures": failures,
                }
                print(f"{model} group {group_name}: {'OK' if ok else failures}", flush=True)
                if ok and entry["selected"] is None:
                    entry["selected"] = list(restores)

        # If no semantic group is sufficient, progressively combine the groups.
        if entry["selected"] is None:
            cumulative = []
            for group_name, restores in GROUPS:
                cumulative.extend(target for target in restores if target not in cumulative)
                ok, failures = parity(opponent, baselines, tuple(cumulative))
                key = f"cumulative_through_{group_name}"
                entry["group_restores"][key] = {
                    "restores": list(cumulative),
                    "ok": ok,
                    "failures": failures,
                }
                print(f"{model} {key}: {'OK' if ok else failures}", flush=True)
                if ok:
                    entry["selected"] = list(cumulative)
                    break

        result["models"][model] = entry

    out = ROOT / "reports" / "newer_native_wrapper_diagnosis.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()

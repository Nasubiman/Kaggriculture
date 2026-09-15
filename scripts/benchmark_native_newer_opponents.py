#!/usr/bin/env python3
"""Probe parity and throughput of native acceleration for newer reference agents."""
from __future__ import annotations

import json
import statistics
import time
from pathlib import Path

import benchmark_native_agent_runtime as base

ROOT = Path(__file__).resolve().parents[1]
MODELS = (
    "public_v38_low_pressure_20260914",
    "public_v41_competitive_20260914",
    "public_v41_survival_20260914",
)
SEED = 13_097_000


def play(opponent: Path, seed: int, seat: int, native: bool, verify: bool):
    tag = f"newer_{opponent.parent.name}_{native}_{seed}_{seat}"
    candidate = base.load_module(ROOT / "main.py", f"candidate_{tag}", True).agent
    rival = base.load_module(opponent, f"rival_{tag}", native).agent
    agents = [candidate, rival] if seat == 0 else [rival, candidate]
    trace = []
    if verify:
        agents = [base.wrap(agent, trace) for agent in agents]
    start = time.perf_counter()
    final = base.runner.run_fast_episode(agents, seed=seed)
    elapsed = time.perf_counter() - start
    state, rewards = base.terminal_fp(final)
    return elapsed, (trace, state), rewards


def main() -> None:
    if not base.agent_runtime.native_acceleration_available():
        raise SystemExit("native accelerator was not imported")

    result = {"models": {}}
    compatible: list[str] = []
    for model in MODELS:
        opponent = ROOT / "test" / model / "main.py"
        model_result = {"parity": True, "seats": {}}
        for seat in (0, 1):
            _, expected, expected_rewards = play(opponent, SEED, seat, False, True)
            _, actual, actual_rewards = play(opponent, SEED, seat, True, True)
            ok = actual == expected and actual_rewards == expected_rewards
            model_result["seats"][str(seat)] = ok
            model_result["parity"] = model_result["parity"] and ok
            print(f"newer opponent parity {model} seat={seat}: {'OK' if ok else 'MISMATCH'}", flush=True)
        if model_result["parity"]:
            compatible.append(model)
        result["models"][model] = model_result

    for model in compatible:
        opponent = ROOT / "test" / model / "main.py"
        samples = {"python": [], "native": []}
        for repeat in range(2):
            variants = [(False, "python"), (True, "native")]
            if repeat & 1:
                variants.reverse()
            for seat in (0, 1):
                for native, name in variants:
                    elapsed, _, _ = play(opponent, SEED + 17 * repeat, seat, native, False)
                    samples[name].append(elapsed)
        py_total = sum(samples["python"])
        native_total = sum(samples["native"])
        result["models"][model]["benchmark"] = {
            "games_per_variant": len(samples["python"]),
            "python_seconds": py_total,
            "native_seconds": native_total,
            "python_median": statistics.median(samples["python"]),
            "native_median": statistics.median(samples["native"]),
            "speedup": py_total / native_total,
        }

    result["compatible_models"] = compatible
    result["incompatible_models"] = [m for m in MODELS if m not in compatible]
    out = ROOT / "reports" / "native_newer_opponents.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()

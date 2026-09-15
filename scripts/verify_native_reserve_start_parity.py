#!/usr/bin/env python3
"""Check whether the corrected r36 reserve window restores full-native parity."""
from __future__ import annotations

import gc
from pathlib import Path

import benchmark_native_agent_runtime as base
from kaggle_environments import make

ROOT = Path(__file__).resolve().parents[1]
MODELS = (
    "public_v31",
    "public_v35",
    "public_v36",
    "public_v38_low_pressure_20260914",
    "public_v41_competitive_20260914",
    "public_v41_survival_20260914",
)
SEEDS = (13_096_000, 13_097_000, 13_098_000)


def play_fast(opponent: Path, seed: int, seat: int, native: bool):
    tag = f"reserve288_{opponent.parent.name}_{native}_{seed}_{seat}"
    candidate = base.load_module(ROOT / "main.py", f"candidate_{tag}", True).agent
    rival = base.load_module(opponent, f"rival_{tag}", native).agent
    trace = []
    agents = [candidate, rival] if seat == 0 else [rival, candidate]
    agents = [base.wrap(agent, trace) for agent in agents]
    gc.collect()
    final = base.runner.run_fast_episode(agents, seed=seed)
    state, rewards = base.terminal_fp(final)
    return trace, state, rewards


def play_official(opponent: Path, seed: int, seat: int, native: bool):
    tag = f"reserve288_official_{opponent.parent.name}_{native}_{seed}_{seat}"
    candidate = base.load_module(ROOT / "main.py", f"candidate_{tag}", True).agent
    rival = base.load_module(opponent, f"rival_{tag}", native).agent
    trace = []
    agents = [candidate, rival] if seat == 0 else [rival, candidate]
    agents = [base.wrap(agent, trace) for agent in agents]
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed}, debug=False)
    env.run(agents)
    state, rewards = base.terminal_fp(env.steps[-1])
    return trace, state, rewards


def main() -> None:
    if not base.agent_runtime.native_acceleration_available():
        raise SystemExit("native accelerator was not imported")
    for model in MODELS:
        opponent = ROOT / "test" / model / "main.py"
        for seed in SEEDS:
            for seat in (0, 1):
                expected = play_fast(opponent, seed, seat, False)
                actual = play_fast(opponent, seed, seat, True)
                assert actual == expected, f"fast mismatch {model} seed={seed} seat={seat}"
                print(f"reserve288 fast parity OK: {model} seed={seed} seat={seat}", flush=True)
    for model in ("public_v38_low_pressure_20260914", "public_v41_competitive_20260914", "public_v41_survival_20260914"):
        opponent = ROOT / "test" / model / "main.py"
        for seat in (0, 1):
            expected = play_official(opponent, 13_099_911, seat, False)
            actual = play_official(opponent, 13_099_911, seat, True)
            assert actual == expected, f"official mismatch {model} seat={seat}"
            print(f"reserve288 official parity OK: {model} seat={seat}", flush=True)


if __name__ == "__main__":
    main()

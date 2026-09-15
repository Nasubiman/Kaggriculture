#!/usr/bin/env python3
"""Verify the shared whitelist reference-runtime policy against Python baselines."""
from __future__ import annotations

import gc
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))

import agent_runtime
import experimental_fast_kaggriculture_v3 as runner
import reference_runtime

MODELS = ("public_v31", "public_v35", "public_v36", "public_v37")
SEEDS = (13_096_000, 13_097_000)
_NATIVE_SLOTS = ("_native", "_reserve_native", "_controller_native", "_chassis_native", "_budget_native")


def load_raw(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_python(path: Path, name: str):
    module = load_raw(path, name)
    saved = {slot: getattr(agent_runtime, slot, None) for slot in _NATIVE_SLOTS}
    try:
        for slot in _NATIVE_SLOTS:
            setattr(agent_runtime, slot, None)
        agent_runtime.optimize_agent_module(module)
    finally:
        for slot, value in saved.items():
            setattr(agent_runtime, slot, value)
    return module


def fp(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def wrap(agent, trace):
    def recorded(obs):
        observation = {k: obs[k] for k in ("step", "player", "farms", "private", "market", "town", "day", "hour")}
        before = fp(observation)
        action = agent(obs)
        trace.append((before, fp(action)))
        return action
    return recorded


def play(model: str, seed: int, seat: int, accelerated: bool):
    path = ROOT / "test" / model / "main.py"
    candidate = load_python(ROOT / "main.py", f"candidate_{model}_{seed}_{seat}_{accelerated}").agent
    if accelerated:
        rival_module = load_raw(path, f"rival_native_{model}_{seed}_{seat}")
        reference_runtime.optimize_reference_agent_module(rival_module, model)
    else:
        rival_module = load_python(path, f"rival_python_{model}_{seed}_{seat}")
    rival = rival_module.agent
    trace = []
    agents = [candidate, rival] if seat == 0 else [rival, candidate]
    agents = [wrap(a, trace) for a in agents]
    gc.collect()
    final = runner.run_fast_episode(agents, seed=seed)
    terminal = [(str(s.status), float(s.reward)) for s in final]
    return trace, terminal


def main() -> None:
    assert not reference_runtime.validated_reference("unknown_model")
    unknown = load_raw(ROOT / "test" / "public_v31" / "main.py", "unknown_reference")
    original_agent = unknown.agent
    reference_runtime.optimize_reference_agent_module(unknown, "unknown_model")
    assert unknown.agent is original_agent

    for model in MODELS:
        assert reference_runtime.validated_reference(model)
        for seed in SEEDS:
            for seat in (0, 1):
                expected = play(model, seed, seat, False)
                actual = play(model, seed, seat, True)
                assert actual == expected, f"reference runtime mismatch {model} seed={seed} seat={seat}"
                print(f"reference runtime parity OK: {model} seed={seed} seat={seat}", flush=True)


if __name__ == "__main__":
    main()

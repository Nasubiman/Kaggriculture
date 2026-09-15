#!/usr/bin/env python3
"""Profile the actual native-enabled training path, not the pure-Python fallback."""
from __future__ import annotations

import cProfile
import importlib.util
import io
import pstats
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))

import agent_runtime
import experimental_fast_kaggriculture_v3 as runner

_NATIVE_SLOTS = ("_native", "_reserve_native", "_controller_native", "_chassis_native", "_budget_native")


def load(path: Path, name: str, native: bool):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    saved = {slot: getattr(agent_runtime, slot, None) for slot in _NATIVE_SLOTS}
    try:
        if not native:
            for slot in _NATIVE_SLOTS:
                setattr(agent_runtime, slot, None)
        agent_runtime.optimize_agent_module(module)
    finally:
        for slot, value in saved.items():
            setattr(agent_runtime, slot, value)
    return module


def profile_once(native: bool) -> tuple[float, str]:
    candidate_module = load(ROOT / "main.py", f"profile_candidate_{native}", native)
    candidate = candidate_module.agent
    rival = load(ROOT / "test" / "public_v37" / "main.py", f"profile_rival_{native}", False).agent
    prof = cProfile.Profile()
    start = time.perf_counter()
    prof.enable()
    runner.run_fast_episode([candidate, rival], seed=13_095_123)
    prof.disable()
    elapsed = time.perf_counter() - start
    out = io.StringIO()
    # Keep full file paths here.  The candidate and public_v37 rival both use a
    # file named main.py; strip_dirs() made their hot functions indistinguishable.
    stats = pstats.Stats(prof, stream=out).sort_stats("cumulative")
    stats.print_stats(100)
    out.write("\n===== self time =====\n")
    stats.sort_stats("tottime").print_stats(100)
    out.write("\n===== dict.get callers =====\n")
    stats.print_callers("get' of 'dict")
    diagnostic = getattr(candidate_module, "_NATIVE_SIMILARITY_DIAGNOSTIC", None)
    if diagnostic is not None:
        out.write("\n===== native similarity diagnostic =====\n")
        out.write(repr(diagnostic) + "\n")
    chassis_diagnostic = getattr(candidate_module, "_NATIVE_CHASSIS_DIAGNOSTIC", None)
    if chassis_diagnostic is not None:
        out.write("\n===== native chassis diagnostic =====\n")
        out.write(repr(chassis_diagnostic) + "\n")
    return elapsed, out.getvalue()


def main() -> None:
    if not agent_runtime.native_acceleration_available():
        raise SystemExit("native accelerator was not imported")
    for native, name in ((False, "python_runtime"), (True, "native_runtime")):
        elapsed, text = profile_once(native)
        print(f"\n===== {name}: elapsed={elapsed:.6f}s =====")
        print(text)


if __name__ == "__main__":
    main()

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


def load(path: Path, name: str, native: bool):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    saved = agent_runtime._native
    try:
        if not native:
            agent_runtime._native = None
        agent_runtime.optimize_agent_module(module)
    finally:
        agent_runtime._native = saved
    return module


def profile_once(native: bool) -> tuple[float, str]:
    candidate = load(ROOT / "main.py", f"profile_candidate_{native}", native).agent
    rival = load(ROOT / "test" / "public_v37" / "main.py", f"profile_rival_{native}", False).agent
    prof = cProfile.Profile()
    start = time.perf_counter()
    prof.enable()
    runner.run_fast_episode([candidate, rival], seed=13_095_123)
    prof.disable()
    elapsed = time.perf_counter() - start
    out = io.StringIO()
    stats = pstats.Stats(prof, stream=out).strip_dirs().sort_stats("cumulative")
    stats.print_stats(100)
    out.write("\n===== self time =====\n")
    stats.sort_stats("tottime").print_stats(100)
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

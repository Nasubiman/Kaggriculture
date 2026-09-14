#!/usr/bin/env python3
"""cProfile the stable and experimental simulator paths on identical agents."""
from __future__ import annotations

import cProfile
import importlib.util
import io
import pstats
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))

import experimental_fast_kaggriculture_v2 as experimental
import fast_kaggriculture as stable


def load_agent(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.agent


def profile_one(name, runner, *, seed=13092000):
    candidate = load_agent(ROOT / "main.py", f"profile_candidate_{name}")
    opponent = load_agent(ROOT / "test/public_v37/main.py", f"profile_opponent_{name}")
    runner.run_fast_episode([candidate, opponent], seed=seed - 1)

    candidate = load_agent(ROOT / "main.py", f"profile_candidate_measured_{name}")
    opponent = load_agent(ROOT / "test/public_v37/main.py", f"profile_opponent_measured_{name}")
    profiler = cProfile.Profile()
    final = profiler.runcall(runner.run_fast_episode, [candidate, opponent], seed=seed)
    assert all(s.status == "DONE" for s in final)

    stream = io.StringIO()
    pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats("cumulative").print_stats(60)
    print(f"\n===== {name}: cumulative =====")
    print(stream.getvalue())

    stream = io.StringIO()
    pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats("tottime").print_stats(60)
    print(f"\n===== {name}: self time =====")
    print(stream.getvalue())


if __name__ == "__main__":
    profile_one("stable", stable)
    profile_one("experimental_v2", experimental)

#!/usr/bin/env python3
"""Reproducible single-process simulation benchmark and full-trajectory parity.

Example (save baseline files before editing):
  .venv/bin/python scripts/benchmark_simulation.py \
    --baseline-agent /tmp/main_before.py --baseline-runner /tmp/runner_before.py \
    --verify --output reports/simulation_benchmark.json

Timing excludes module loading, verification, and one warm-up game per variant.
Every measured game still gets fresh agent modules to isolate module globals.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import importlib.util
import json
import platform
import statistics
import sys
import time
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def play(runner, agent_path, opponent_path, seed, seat, verify=False):
    agents = [load_module(agent_path, "benchmark_candidate").agent,
              load_module(opponent_path, "benchmark_opponent").agent]
    if seat:
        agents.reverse()
    trace = []
    if verify:
        def wrap(agent):
            def recorded(obs):
                # Framework timing metadata is excluded; all game fields remain.
                observation = {k: obs[k] for k in (
                    "step", "player", "farms", "private", "market", "town", "day", "hour"
                )}
                before = fingerprint(observation)
                action = agent(obs)
                trace.append((before, fingerprint(action)))
                return action
            return recorded
        agents = [wrap(agent) for agent in agents]
    # Freshly imported agents form large function/global reference cycles. Do
    # not charge collection of a previous A/B variant to this variant's game.
    # Collection remains enabled during the measured episode.
    gc.collect()
    start = time.perf_counter()
    if runner is None:
        from kaggle_environments import make
        env = make("kaggriculture", configuration={"seed": seed, "episodeSteps": 720})
        env.run(agents)
        final = env.state
    else:
        final = runner.run_fast_episode(agents, seed=seed)
    elapsed = time.perf_counter() - start
    terminal = [{"status": s.status, "reward": s.reward,
                 "observation": {k: v for k, v in s.observation.items()
                                 if k not in ("step", "remainingOverageTime")}}
                for s in final]
    assert all(s.status == "DONE" for s in final), terminal
    return elapsed, (trace, fingerprint(terminal)), [s.reward for s in final]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", type=Path, default=ROOT / "main.py")
    parser.add_argument("--baseline-agent", type=Path)
    parser.add_argument("--baseline-runner", type=Path)
    parser.add_argument("--models", nargs="+", default=["public_v31", "public_v35", "public_v36", "public_v37"])
    parser.add_argument("--seeds", type=int, default=2)
    parser.add_argument("--seed-start", type=int, default=13_090_000)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "reports/simulation_benchmark.json")
    args = parser.parse_args()
    if args.seeds < 1 or args.repeats < 1:
        parser.error("seeds and repeats must be positive")
    current = load_module(ROOT / "training/fast_kaggriculture.py", "benchmark_current")
    variants = {"optimized": (current, args.agent)}
    if args.baseline_agent or args.baseline_runner:
        baseline = (load_module(args.baseline_runner, "benchmark_baseline")
                    if args.baseline_runner else current)
        variants = {"baseline": (baseline, args.baseline_agent or args.agent), **variants}
    tasks = [(ROOT / "test" / model / "main.py", args.seed_start + 17 * i, seat)
             for model in args.models for i in range(args.seeds) for seat in (0, 1)]
    parity = 0
    standard_parity = 0
    if args.verify:
        for opponent, seed, seat in tasks:
            expected = None
            for name, (runner, agent) in variants.items():
                _, trace, _ = play(runner, agent, opponent, seed, seat, True)
                if expected is None:
                    expected = trace
                assert trace == expected, f"trajectory mismatch: {name}, {opponent}, {seed}, {seat}"
            parity += 1
            # Both seats of each opponent, first seed, also use official runner.
            if seed == args.seed_start:
                _, standard, _ = play(None, args.agent, opponent, seed, seat, True)
                assert standard == expected, f"standard mismatch: {opponent}, {seed}, {seat}"
                standard_parity += 1
            print(f"parity OK: {opponent.parent.name} seed={seed} seat={seat}", flush=True)
    for runner, agent in variants.values():
        play(runner, agent, *tasks[0])
    samples = {name: [] for name in variants}
    for repeat in range(args.repeats):
        # Alternate A/B order to reduce systematic warm-up / thermal bias.
        names = list(variants)
        if repeat % 2:
            names.reverse()
        for opponent, seed, seat in tasks:
            rewards = None
            for name in names:
                runner, agent = variants[name]
                elapsed, _, result = play(runner, agent, opponent, seed, seat)
                assert rewards is None or rewards == result, "benchmark reward mismatch"
                rewards = result
                samples[name].append(elapsed)
        print(f"timing repeat {repeat + 1}/{args.repeats} complete", flush=True)
    report = {
        "platform": platform.platform(), "python": sys.version,
        "kaggle_environments": version("kaggle-environments"),
        "models": args.models, "seeds": args.seeds, "seed_start": args.seed_start,
        "repeats": args.repeats, "trajectory_games": parity,
        "standard_trajectory_games": standard_parity,
        "source_sha256": {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in [args.agent, ROOT / "training/fast_kaggriculture.py",
                                    args.baseline_agent, args.baseline_runner,
                                    *(task[0] for task in tasks)] if p},
        "timing_scope": "single process; excludes imports, pre-game GC and warm-up; fresh agents per game; GC enabled during play",
        "results": {name: {"games": len(times), "seconds": sum(times),
                           "games_per_second": len(times) / sum(times),
                           "median_seconds": statistics.median(times), "samples_seconds": times}
                    for name, times in samples.items()},
    }
    if "baseline" in samples:
        report["speedup"] = sum(samples["baseline"]) / sum(samples["optimized"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k not in ("results", "source_sha256")}, indent=2))
    for name, result in report["results"].items():
        print(f"{name}: {result['games_per_second']:.3f} games/s")


if __name__ == "__main__":
    main()

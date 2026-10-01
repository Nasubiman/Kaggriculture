#!/usr/bin/env python3
"""Per-step decision time of agent files (Kaggle last-callable semantics).

Usage: python scripts/timing.py AGENT [AGENT ...] [--opponent PATH] [--seed N]
"""
from __future__ import annotations

import argparse
import importlib.util
import time

from kaggle_environments import make


def load(path):
    spec = importlib.util.spec_from_file_location("m" + str(abs(hash(path))), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return [v for v in vars(module).values() if callable(v)][-1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("agents", nargs="+")
    ap.add_argument("--opponent", default="agents/results31.py")
    ap.add_argument("--seed", type=int, default=13400051)
    a = ap.parse_args()
    opponent = load(a.opponent)
    for path in a.agents:
        agent = load(path)
        times = []

        def timed(obs, cfg=None, agent=agent):
            t0 = time.perf_counter()
            action = agent(obs, cfg)
            times.append(time.perf_counter() - t0)
            return action

        env = make("kaggriculture", configuration={"seed": a.seed, "episodeSteps": 720})
        env.run([timed, opponent])
        times.sort()
        print("%s steps %d mean %.1fms p99 %.1fms max %.1fms reward %s %s" % (
            path, len(times), 1000 * sum(times) / len(times), 1000 * times[int(0.99 * len(times))],
            1000 * times[-1], env.state[0]["reward"], env.state[1]["reward"]))


if __name__ == "__main__":
    main()

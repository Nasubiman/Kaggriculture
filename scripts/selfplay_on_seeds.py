#!/usr/bin/env python3
"""Play candidate vs opponent on explicit seeds (both from single-file agents)."""
from __future__ import annotations
import argparse, json, multiprocessing as mp, os, sys
from pathlib import Path
from statistics import mean
from kaggle_environments.agent import get_last_callable
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))
_A = {}
def _load(path):
    if path not in _A:
        _A[path] = get_last_callable(Path(path).read_text(), path=path)
    return _A[path]
def play(task):
    cand, opp, seed, seat = task
    from production_fast_kaggriculture import run_fast_episode
    try:
        a, b = _load(cand), _load(opp)
        agents = [a, b] if seat == 0 else [b, a]
        final = run_fast_episode(agents, seed=seed)
        r, o = float(final[seat].reward), float(final[1 - seat].reward)
        return {"seed": seed, "seat": seat, "reward": r, "opponent_reward": o, "margin": r - o, "win": r > o, "error": None}
    except Exception as e:
        return {"seed": seed, "seat": seat, "error": repr(e), "reward": 0, "opponent_reward": 0, "margin": 0, "win": False}
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--candidate", default=str(ROOT / "main.py"))
    p.add_argument("--opponent", default=str(ROOT / "main.py"))
    p.add_argument("--seeds", nargs="*", type=int, default=[])
    p.add_argument("--seeds-file")
    p.add_argument("--both-seats", action="store_true")
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--output")
    a = p.parse_args()
    seeds = list(a.seeds)
    if a.seeds_file:
        seeds += [int(x) for x in Path(a.seeds_file).read_text().split()]
    tasks = [(str(Path(a.candidate).resolve()), str(Path(a.opponent).resolve()), s, seat)
             for s in seeds for seat in ((0, 1) if a.both_seats else (0,))]
    with mp.get_context("spawn").Pool(min(a.workers, os.cpu_count() or 1)) as pool:
        rows = list(pool.imap_unordered(play, tasks, chunksize=1))
    ok = [r for r in rows if r["error"] is None]
    s = {"games": len(rows), "errors": len(rows) - len(ok),
         "wins": sum(r["win"] for r in ok), "mean_reward": mean(r["reward"] for r in ok),
         "mean_opponent_reward": mean(r["opponent_reward"] for r in ok),
         "mean_margin": mean(r["margin"] for r in ok)}
    print(json.dumps(s))
    if a.output:
        Path(a.output).write_text(json.dumps({"summary": s, "games": rows}))
if __name__ == "__main__":
    main()

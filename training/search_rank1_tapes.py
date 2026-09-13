#!/usr/bin/env python3
"""Race every observed rank-1 action tape against a diverse opponent league."""

from __future__ import annotations

import argparse
from collections import defaultdict
import importlib.util
import json
import multiprocessing as mp
import os
from pathlib import Path
from statistics import mean

from fast_kaggriculture import run_fast_episode


_CANDIDATES = {}; _OPPONENTS = {}; _CANDIDATE_PATHS = {}; _OPPONENT_PATHS = {}


def load_agent(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None: raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module.agent


def worker_init(candidates, opponents):
    global _CANDIDATES, _OPPONENTS, _CANDIDATE_PATHS, _OPPONENT_PATHS
    _CANDIDATES = {}; _OPPONENTS = {}; _CANDIDATE_PATHS = candidates; _OPPONENT_PATHS = opponents


def play(task):
    candidate, opponent, seed, seat = task
    try:
        policy = _CANDIDATES.get(candidate)
        if policy is None:
            policy = load_agent(Path(_CANDIDATE_PATHS[candidate]), f"tape_{os.getpid()}_{candidate}"); _CANDIDATES[candidate] = policy
        rival = _OPPONENTS.get(opponent)
        if rival is None:
            rival = load_agent(Path(_OPPONENT_PATHS[opponent]), f"rival_{os.getpid()}_{opponent}"); _OPPONENTS[opponent] = rival
        final = run_fast_episode([policy, rival] if seat == 0 else [rival, policy], seed=seed)
        reward = float(final[seat].reward); other = float(final[1-seat].reward)
        return candidate, opponent, reward, reward-other, reward>other, None
    except Exception as error:
        return candidate, opponent, -1e6, -1e6, False, repr(error)


def race(pool, candidates, opponents, seeds, seed_start):
    tasks = [(candidate, opponent, seed_start+seed*17, seat) for candidate in candidates
             for opponent in opponents for seed in range(seeds) for seat in (0,1)]
    raw = list(pool.imap_unordered(play, tasks, chunksize=4)); grouped = defaultdict(list)
    for row in raw: grouped[row[0]].append(row)
    result = []
    for candidate, rows in grouped.items():
        per_opponent = {}
        for opponent in opponents:
            values = [row for row in rows if row[1] == opponent]
            per_opponent[opponent] = {"reward":mean(row[2] for row in values), "margin":mean(row[3] for row in values),
                                      "win_rate":mean(row[4] for row in values)}
        result.append({"candidate":candidate, "games":len(rows), "errors":sum(row[5] is not None for row in rows),
                       "reward":mean(row[2] for row in rows), "margin":mean(row[3] for row in rows),
                       "win_rate":mean(row[4] for row in rows),
                       "worst_reward":min(value["reward"] for value in per_opponent.values()),
                       "opponents":per_opponent})
    result.sort(key=lambda row:(row["errors"] == 0, row["reward"]+.15*row["margin"], row["worst_reward"]), reverse=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates-dir", type=Path, required=True); parser.add_argument("--models-dir", type=Path, required=True)
    parser.add_argument("--stage0-opponents", nargs="+", default=["attack_roundtrip_first25","incumbent_v37_opening","results5_20260913"])
    parser.add_argument("--stage1-opponents", nargs="+", default=["attack_roundtrip_first25","attack_roundtrip_q90","incumbent_roundtrip_first35","incumbent_v37_opening","public_v31","public_v35","public_v36","public_v37","results4_20260913","results5_20260913"])
    parser.add_argument("--stage0-seeds", type=int, default=2); parser.add_argument("--stage1-seeds", type=int, default=10)
    parser.add_argument("--finalists", type=int, default=20); parser.add_argument("--workers", type=int, default=20)
    parser.add_argument("--seed-start", type=int, default=13000000); parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    candidates = {path.parent.name:str(path.resolve()) for path in args.candidates_dir.glob("*/main.py")}
    opponent_names = sorted(set(args.stage0_opponents+args.stage1_opponents))
    opponents = {name:str((args.models_dir/name/"main.py").resolve()) for name in opponent_names}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    context = mp.get_context("spawn")
    with context.Pool(args.workers, initializer=worker_init, initargs=(candidates,opponents)) as pool:
        stage0 = race(pool, list(candidates), args.stage0_opponents, args.stage0_seeds, args.seed_start)
        (args.output_dir/"stage0.json").write_text(json.dumps(stage0,indent=2)+"\n")
        finalists = [row["candidate"] for row in stage0[:args.finalists]]
        print("stage0", [(r["candidate"],round(r["reward"])) for r in stage0[:10]], flush=True)
        stage1 = race(pool, finalists, args.stage1_opponents, args.stage1_seeds, args.seed_start+100003)
        (args.output_dir/"stage1.json").write_text(json.dumps(stage1,indent=2)+"\n")
        print("stage1", [(r["candidate"],round(r["reward"]),round(r["win_rate"]*100,1)) for r in stage1[:10]], flush=True)
    best = stage1[0]
    (args.output_dir/"best.json").write_text(json.dumps(best,indent=2)+"\n")
    print("best", best["candidate"], best["reward"], best["margin"], best["win_rate"])


if __name__ == "__main__": main()

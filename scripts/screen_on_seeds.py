#!/usr/bin/env python3
"""Play every candidate file against every opponent on an explicit seed list (both seats).

Writes <output_dir>/<candidate>.json with one row per game, so variants can be
compared on identical (opponent, seed, seat) games.
"""
from __future__ import annotations
import argparse, json, multiprocessing as mp, os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))
_A = {}


def _load(path):
    from kaggle_environments.agent import get_last_callable
    return get_last_callable(Path(path).read_text(), path=path)


def play(task):
    cand, opp, seed, seat = task
    from production_fast_kaggriculture import run_fast_episode
    # Kaggle runs an agent from its own folder; some read sibling files by relative path.
    cand, opp = str(Path(cand).resolve()), str(Path(opp).resolve())
    os.chdir(Path(cand).parent)
    try:
        a, b = _load(cand), _load(opp)
        seen = {}

        def spy(obs, cfg=None, _a=a):
            if int(obs["step"]) == 144:
                seen["pair"] = "|".join((obs.get("town") or {}).get("unlocked_shops", [])[:2])
            return _a(obs, cfg)
        agents = [spy, b] if seat == 0 else [b, spy]
        f = run_fast_episode(agents, seed=seed)
        r, o = float(f[seat].reward), float(f[1 - seat].reward)
        return {"candidate": Path(cand).stem, "model": Path(opp).parent.name, "seed": seed, "seat": seat,
                "reward": r, "opponent_reward": o, "margin": r - o, "win": r > o, "tie": r == o, "pair": seen.get("pair"), "error": None}
    except Exception as e:
        return {"candidate": Path(cand).stem, "model": Path(opp).parent.name, "seed": seed, "seat": seat, "error": repr(e)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--candidates", nargs="+", required=True)
    p.add_argument("--opponents", nargs="+", required=True)
    p.add_argument("--seeds-file", type=Path, required=True)
    p.add_argument("--seed-class", help="key in a JSON seed-class map")
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--workers", type=int, default=20)
    a = p.parse_args()
    if a.seed_class:
        seeds = [int(x) for x in json.loads(a.seeds_file.read_text())[a.seed_class]]
    else:
        seeds = [int(x) for x in a.seeds_file.read_text().split()]
    a.output_dir.mkdir(parents=True, exist_ok=True)
    ctx = mp.get_context("spawn")
    for cand in a.candidates:
        out = a.output_dir / (Path(cand).stem + ".json")
        if out.exists():
            continue
        tasks = [(str(Path(cand).resolve()), str(Path(o).resolve()), s, seat)
                 for o in a.opponents for s in seeds for seat in (0, 1)]
        with ctx.Pool(a.workers) as pool:
            rows = list(pool.imap_unordered(play, tasks, chunksize=2))
        out.write_text(json.dumps({"games": rows}))
        print("done", Path(cand).stem, len(rows), "errors", sum(1 for r in rows if r.get("error")), flush=True)
    print("ALLDONE", flush=True)


if __name__ == "__main__":
    main()

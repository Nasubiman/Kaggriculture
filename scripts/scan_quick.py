#!/usr/bin/env python3
"""One quick game per candidate file vs an opponent (each in its own subprocess with a timeout).

Prints one JSON line per file: reward, opponent reward, error. Used to discard
non-agents and clearly weak agents before a proper screen.
"""
import argparse, json, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
CHILD = r'''
import json, os, sys
sys.path.insert(0, %(train)r)
cand, opp, seed = %(cand)r, %(opp)r, %(seed)d
os.chdir(os.path.dirname(cand)); sys.path.insert(0, os.path.dirname(cand))
from kaggle_environments.agent import get_last_callable
from production_fast_kaggriculture import run_fast_episode
a = get_last_callable(open(cand, encoding="utf-8").read(), path=cand)
n = getattr(getattr(a, "__code__", None), "co_argcount", 2)
if hasattr(a, "__self__"): n -= 1
f = (lambda o, c=None: a(o, c if c is not None else {"episodeSteps": 720})) if n >= 2 else (lambda o, c=None: a(o))
b = get_last_callable(open(opp).read(), path=opp)
r = run_fast_episode([f, b], seed=seed)
print("RESULT" + json.dumps([float(r[0].reward), float(r[1].reward), r[0].status]))
'''


def run(task):
    cand, opp, seed, timeout = task
    code = CHILD % {"train": str(ROOT / "training"), "cand": cand, "opp": opp, "seed": seed}
    try:
        p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=timeout,
                           env={"OMP_NUM_THREADS": "1", "PATH": "/usr/bin:/bin", "HOME": "/tmp"})
        line = [l for l in p.stdout.splitlines() if l.startswith("RESULT")]
        if line:
            r, o, st = json.loads(line[-1][6:])
            return {"file": cand, "reward": r, "opp": o, "margin": r - o, "status": st}
        return {"file": cand, "error": (p.stderr.strip().splitlines() or ["no output"])[-1][:200]}
    except subprocess.TimeoutExpired:
        return {"file": cand, "error": "timeout"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", type=Path, required=True)
    ap.add_argument("--opponent", required=True)
    ap.add_argument("--seed", type=int, default=9950000)
    ap.add_argument("--timeout", type=int, default=240)
    ap.add_argument("--workers", type=int, default=20)
    ap.add_argument("--output", type=Path, required=True)
    a = ap.parse_args()
    files = [str(Path(l).resolve()) for l in a.list.read_text().split("\n") if l.strip()]
    opp = str(Path(a.opponent).resolve())
    with ThreadPoolExecutor(a.workers) as ex, a.output.open("w") as out:
        for row in ex.map(run, [(f, opp, a.seed, a.timeout) for f in files]):
            out.write(json.dumps(row) + "\n"); out.flush()


if __name__ == "__main__":
    main()

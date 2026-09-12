"""Measure fresh imports, gameplay and garbage collection in alternating batches.

Pass saved pre-change main.py and fast_kaggriculture.py as the two arguments.
Run from the repository root after stopping other performance benchmarks.
"""
import argparse
import gc
import importlib.util
import json
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path('training').resolve()))
def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline_agent', type=Path)
    parser.add_argument('baseline_runner', type=Path)
    parser.add_argument('--output', type=Path, default=Path('reports/simulation_speedup_lifecycle_20260913.json'))
    args = parser.parse_args()
    variants = {
     'baseline': (module(args.baseline_runner,'oldrunner'), args.baseline_agent),
     'optimized': (module('training/fast_kaggriculture.py','newrunner'),Path('main.py')),
    }
    def game(runner, path, opponent, seat, seed):
        agents = [module(path,'candidate').agent, module(opponent,'opponent').agent]
        if seat: agents.reverse()
        final = runner.run_fast_episode(agents,seed=seed)
        assert all(s.status == 'DONE' for s in final)
        return [s.reward for s in final]
    tasks = [(Path('test')/model/'main.py',seat,13090000) for model in ['public_v31','public_v35','public_v36','public_v37'] for seat in (0,1)]
    for runner,path in variants.values(): game(runner,path,*tasks[0])
    rows=[]
    for repeat in range(3):
        names = list(variants) if repeat%2==0 else list(reversed(variants))
        expected=None
        for name in names:
            runner,path = variants[name]
            gc.collect()
            start=time.perf_counter()
            rewards=[game(runner,path,*task) for task in tasks]
            gc.collect()
            elapsed=time.perf_counter()-start
            assert expected is None or rewards == expected
            expected=rewards
            rows.append(dict(variant=name,repeat=repeat,games=len(tasks),seconds=elapsed))
            print(rows[-1],flush=True)
    totals={name:sum(r['seconds'] for r in rows if r['variant']==name) for name in variants}
    result={'scope':'single-process batches; includes fresh agent imports, play, and cyclic garbage collection; excludes one warm-up game per variant','games_per_variant':24,'rows':rows,'speedup':totals['baseline']/totals['optimized'],'games_per_second':{name:24/t for name,t in totals.items()}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(result,flush=True)


if __name__ == "__main__":
    main()

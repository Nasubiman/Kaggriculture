#!/usr/bin/env python3
"""Per shop-pair tape (route) search for the current main.py.

main.py picks its action tape at step 144 from the first two opened shops.
This tool overrides that choice for one shop pair at a time and plays paired
games, so every pair can use whichever tape actually wins most for it.

  map     : play main.py vs main.py to step 145 and record each seed's shop pair
  search  : for each pair, play every candidate route on that pair's seeds
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))

ROUTER_LINE = "        state['route']=_V92_TABLE.get(shops,state['route'])\n"
_CODE = {}
_OPP = {}


def _candidate_source(path: str) -> str:
    src = Path(path).read_text()
    if src.count(ROUTER_LINE) != 1:
        raise SystemExit("router line not found exactly once")
    return src.replace(ROUTER_LINE, ROUTER_LINE + "        state['route']=globals().get('_PAIR_OVERRIDE',{}).get(shops,state['route'])\n")


_EXTRA = {}


def load_extra_routes(spec: str | None) -> dict:
    """{route_id: tape_file} -> {route_id: list of 720 action dicts}."""
    if not spec:
        return {}
    if spec not in _EXTRA:
        table = json.loads(Path(spec).read_text())
        _EXTRA[spec] = {int(k): json.loads(Path(v).read_text()) for k, v in table.items()}
    return _EXTRA[spec]


def load_candidate(path: str, override: dict, extra: dict | None = None):
    """Fresh module per game: the tape override is baked into its globals."""
    code = _CODE.get(path)
    if code is None:
        code = _CODE[path] = compile(_candidate_source(path), path, "exec")
    env = {"__name__": "route_candidate", "__file__": path, "_PAIR_OVERRIDE": dict(override)}
    exec(code, env)
    if extra:
        # recorded tapes join the chassis library under new route ids
        routes = env["_IMPL"].chassis.routes
        for rid, tape in extra.items():
            routes[rid] = [dict(a) for a in tape]
    return [v for v in env.values() if callable(v)][-1]


def load_opponent(path: str):
    from kaggle_environments.agent import get_last_callable
    return get_last_callable(Path(path).read_text(), path=path)


def map_seed(task):
    seed, candidate = task
    from production_fast_kaggriculture import create_fast_episode, run_fast_steps
    a, b = load_candidate(candidate, {}), load_candidate(candidate, {})
    env, state = create_fast_episode(seed=seed)
    stop = int(os.environ.get("MAP_STOP_STEP", "145"))
    state = run_fast_steps([a, b], env=env, state=state, stop_step=stop)
    shops = list(state[0].observation["town"]["unlocked_shops"][: 3 if stop > 216 else 2])
    return seed, shops


def record(task):
    """Play the candidate and keep every action it actually submitted."""
    candidate, opponent, seed, out = task
    from production_fast_kaggriculture import run_fast_episode
    agent = load_candidate(candidate, {})
    actions = []

    def spy(obs, cfg=None):
        a = agent(obs, cfg)
        actions.append({"farmer": list(a.get("farmer") or ["PASS"]),
                        "hands": [list(h) for h in (a.get("hands") or [])],
                        "market": [list(o) for o in (a.get("market") or [])]})
        return a

    final = run_fast_episode([spy, load_opponent(opponent)], seed=seed)
    while len(actions) < 720:
        actions.append({"farmer": ["PASS"], "hands": [], "market": []})
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(actions))
    return seed, out, float(final[0].reward), float(final[1].reward)


_EXTRA_SPEC = None


def play(task):
    candidate, opponent, pair, route, seed, seat = task[:6]
    extra_spec = task[6] if len(task) > 6 else None
    from production_fast_kaggriculture import run_fast_episode
    seen = {}
    try:
        agent = load_candidate(candidate, {} if route is None else {tuple(pair): route},
                               load_extra_routes(extra_spec))

        def spy(obs, cfg=None):
            if int(obs["step"]) == 144:
                seen["pair"] = list(obs["town"]["unlocked_shops"][:2])
            return agent(obs, cfg)

        opp = load_opponent(opponent)
        agents = [spy, opp] if seat == 0 else [opp, spy]
        final = run_fast_episode(agents, seed=seed)
        r, o = float(final[seat].reward), float(final[1 - seat].reward)
        return {"pair": pair, "route": route, "seed": seed, "seat": seat,
                "opponent": Path(opponent).parent.name, "reward": r, "opponent_reward": o,
                "margin": r - o, "win": r > o, "seen_pair": seen.get("pair"), "error": None}
    except Exception as error:
        return {"pair": pair, "route": route, "seed": seed, "seat": seat,
                "opponent": Path(opponent).parent.name, "error": repr(error)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=["map", "search", "record"])
    p.add_argument("--extra-routes", help="JSON {route_id: recorded tape file} added to the tape library")
    p.add_argument("--record-plan", type=Path, help="record mode: JSON [[seed, output_file], ...]")
    p.add_argument("--record-opponent", default=str(ROOT / "main.py"))
    p.add_argument("--candidate", default=str(ROOT / "main.py"))
    p.add_argument("--seed-start", type=int, default=12_000_000)
    p.add_argument("--seeds", type=int, default=4000)
    p.add_argument("--map-file", type=Path, default=ROOT / "reports/seed_shop_pairs.json")
    p.add_argument("--per-pair", type=int, default=16)
    p.add_argument("--skip-per-pair", type=int, default=0, help="skip the first N seeds of each pair (fresh validation)")
    p.add_argument("--opponents", nargs="+", default=[])
    p.add_argument("--routes", type=Path, help="JSON {\"A|B\": [routes...]} of candidates; null = native")
    p.add_argument("--pairs", nargs="*", default=[])
    p.add_argument("--workers", type=int, default=20)
    p.add_argument("--output", type=Path)
    a = p.parse_args()
    ctx = mp.get_context("spawn")
    if a.mode == "map":
        seeds = [a.seed_start + i for i in range(a.seeds)]
        with ctx.Pool(a.workers) as pool:
            rows = pool.map(map_seed, [(s, a.candidate) for s in seeds], chunksize=4)
        mapping = {str(s): pair for s, pair in rows}
        a.map_file.parent.mkdir(parents=True, exist_ok=True)
        a.map_file.write_text(json.dumps(mapping))
        pairs = {}
        for pair in mapping.values():
            pairs["|".join(pair[:2])] = pairs.get("|".join(pair[:2]), 0) + 1
        print(len(mapping), "seeds,", len(pairs), "pairs; min per pair", min(pairs.values()))
        return
    if a.mode == "record":
        plan = json.loads(a.record_plan.read_text())
        with ctx.Pool(a.workers) as pool:
            rows = pool.map(record, [(a.candidate, a.record_opponent, int(s), o) for s, o in plan])
        for r in rows:
            print("recorded", r)
        return
    mapping = json.loads(a.map_file.read_text())
    by_pair = {}
    for s, pair in mapping.items():
        by_pair.setdefault("|".join(pair[:2]), []).append(int(s))
    routes = json.loads(a.routes.read_text())
    tasks = []
    for key, candidates in routes.items():
        if a.pairs and key not in a.pairs:
            continue
        seeds = sorted(by_pair.get(key, []))[a.skip_per_pair: a.skip_per_pair + a.per_pair]
        for route in candidates:
            for seed in seeds:
                for seat in (0, 1):
                    for opp in a.opponents:
                        tasks.append((a.candidate, opp, key.split("|"), route, seed, seat, a.extra_routes))
    print(len(tasks), "games", flush=True)
    with ctx.Pool(a.workers) as pool:
        rows = list(pool.imap_unordered(play, tasks, chunksize=2))
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(rows))
    errors = sum(1 for r in rows if r.get("error"))
    print("done", len(rows), "errors", errors)


if __name__ == "__main__":
    main()

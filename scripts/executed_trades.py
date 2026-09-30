#!/usr/bin/env python3
"""Measure executed market trades by re-simulating public replays.

Both seats replay their recorded actions in kaggle-environments; a hook around
_process_market records, per player and step, the change in shed stock and
the market prices before/after. Executed sells = shed decrease of a product
during the market phase; revenue is approximated with the mean of the pre- and
post-trade prices. Also checks that the re-simulated rewards match the record.
"""
from __future__ import annotations

import argparse
import copy
import json
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor

PRODUCTS = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER"]


def tape(actions):
    def agent(observation, configuration=None):
        step = int(observation.get("step", 0))
        if step + 1 < len(actions) and isinstance(actions[step + 1], dict):
            a = dict(actions[step + 1])
            p = int(observation.get("player", 0))
            a["hands"] = list(a.get("hands") or [])[: len(observation["farms"][p].get("hands") or [])]
            return a
        return {"farmer": ["PASS"], "hands": [], "market": []}
    return agent


def run(job):
    path, players = job
    import kaggle_environments.envs.kaggriculture.kaggriculture as K
    from kaggle_environments import make
    d = json.load(open(path))
    steps = d["steps"]
    log = []
    original = K._process_market

    def hooked(state, env):
        obs0 = state[0].observation
        step = int(K.get(obs0, "step", 0))
        before = [dict(s.observation.private.shed) for s in state]
        money0 = [float(f["money"]) for f in obs0.farms]
        p0 = dict(obs0.market.prices)
        out = original(state, env)
        p1 = dict(state[0].observation.market.prices)
        after = [dict(s.observation.private.shed) for s in state]
        money1 = [float(f["money"]) for f in state[0].observation.farms]
        log.append((step, before, after, p0, p1, money0, money1))
        return out

    K._process_market = hooked
    try:
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": int(d["info"]["seed"])}, debug=False)
        env.run([tape([s[0].get("action") for s in steps]), tape([s[1].get("action") for s in steps])])
    finally:
        K._process_market = original
    rewards = [env.state[0].reward, env.state[1].reward]
    res = []
    for p in players:
        sold = Counter(); rev = Counter(); bought = Counter(); phase = defaultdict(Counter); sell_turns = Counter()
        spend = 0.0; spend_by_day = Counter()
        for step, before, after, p0, p1, m0, m1 in log:
            step_rev = 0.0
            for it in PRODUCTS:
                dlt = int(after[p].get(it, 0)) - int(before[p].get(it, 0))
                if dlt < 0:
                    n = -dlt
                    sold[it] += n; rev[it] += n * (p0[it] + p1[it]) / 2; sell_turns[it] += 1
                    step_rev += n * (p0[it] + p1[it]) / 2
                    ph = "d0-11" if step < 288 else ("d12-19" if step < 480 else ("d20-26" if step < 648 else "d27-29"))
                    phase[ph][it] += n
                elif dlt > 0:
                    bought[it] += dlt
            cost = step_rev - (m1[p] - m0[p])
            if cost > 1:
                spend += cost; spend_by_day[step // 24] += cost
        res.append({
            "replay": path.split("/")[-1], "player": p, "team": d["info"]["TeamNames"][p],
            "reward": rewards[p], "recorded_reward": d["rewards"][p],
            "sold": dict(sold), "revenue": {k: round(v) for k, v in rev.items()},
            "bought": dict(bought), "phase": {k: dict(v) for k, v in phase.items()},
            "sell_turns": dict(sell_turns),
            "spend": round(spend), "spend_by_day": {k: round(v) for k, v in spend_by_day.items()},
            "hands_by_day": [len((steps[min(d * 24, len(steps) - 1)][0]["observation"]["farms"][p].get("hands") or [])) for d in range(30)],
        })
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--players", required=True, help="JSON [[label, replay_path, player], ...]")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--output", required=True)
    a = ap.parse_args()
    items = json.load(open(a.players))
    by_path = defaultdict(list); label_of = {}
    for label, path, p in items:
        by_path[path].append(int(p)); label_of[(path.split("/")[-1], int(p))] = label
    out = []
    with ProcessPoolExecutor(a.workers) as ex:
        for rows in ex.map(run, list(by_path.items())):
            for r in rows:
                r["label"] = label_of[(r["replay"], r["player"])]
                out.append(r)
                ok = "OK" if abs(r["reward"] - r["recorded_reward"]) < 1 else "MISMATCH"
                print(r["label"], r["team"][:20], r["reward"], r["recorded_reward"], ok, flush=True)
    json.dump(out, open(a.output, "w"))


if __name__ == "__main__":
    main()

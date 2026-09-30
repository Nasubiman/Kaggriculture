#!/usr/bin/env python3
"""Replay one candidate-vs-opponent game and show where the margin moved.

Records, per day, the money margin and per item the executed sales revenue
(mean of pre/post price) and purchase cost of each seat, then prints the days
and items with the largest swings. Optionally dumps market orders for a step
range.
"""
from __future__ import annotations

import argparse
import importlib.util
from collections import Counter, defaultdict

import kaggle_environments.envs.kaggriculture.kaggriculture as K
from kaggle_environments import make

P = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER"]


def load(path):
    spec = importlib.util.spec_from_file_location("m" + str(abs(hash(path))), path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return [v for v in vars(m).values() if callable(v)][-1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", required=True)
    ap.add_argument("--opponent", required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--seat", type=int, default=0)
    ap.add_argument("--orders", default="", help="step range a:b to dump orders")
    a = ap.parse_args()
    A, B = load(a.agent), load(a.opponent)
    log = []
    orig = K._process_market

    def hooked(state, env):
        st = int(K.get(state[0].observation, "step", 0))
        b = [dict(x.observation.private.shed) for x in state]
        p0 = dict(state[0].observation.market.prices)
        m0 = [float(f["money"]) for f in state[0].observation.farms]
        orders = [list((x.action or {}).get("market") or []) if isinstance(x.action, dict) else [] for x in state]
        r = orig(state, env)
        a_ = [dict(x.observation.private.shed) for x in state]
        p1 = dict(state[0].observation.market.prices)
        m1 = [float(f["money"]) for f in state[0].observation.farms]
        log.append((st, b, a_, p0, p1, m0, m1, orders))
        return r

    K._process_market = hooked
    agents = [A, B] if a.seat == 0 else [B, A]
    env = make("kaggriculture", configuration={"seed": a.seed, "episodeSteps": 720}); env.run(agents)
    K._process_market = orig
    me, op = a.seat, 1 - a.seat
    print("final", env.state[me].reward, "vs", env.state[op].reward, "margin", env.state[me].reward - env.state[op].reward)
    rev = [defaultdict(Counter), defaultdict(Counter)]
    cost = [defaultdict(Counter), defaultdict(Counter)]
    daymargin = {}
    for st, b, a_, p0, p1, m0, m1, orders in log:
        day = st // 24
        daymargin[day] = m1[me] - m1[op]
        for p in (me, op):
            sold_value = 0.0
            for it in P:
                d = int(a_[p].get(it, 0)) - int(b[p].get(it, 0))
                if d < 0:
                    v = -d * (p0[it] + p1[it]) / 2
                    rev[p][day][it] += v; sold_value += v
            spent = sold_value - (m1[p] - m0[p])
            if spent > 1:
                kinds = sorted({o[0] + (":" + o[1] if len(o) > 1 and o[0] == "BUY_PRODUCT" else "") for o in orders[p] if o and o[0] != "SELL"})
                cost[p][day]["|".join(kinds) or "?"] += spent
    prev = 0
    print("day  margin   dMargin   top item revenue diffs (me-op)            spend diff")
    for day in sorted(daymargin):
        dm = daymargin[day] - prev; prev = daymargin[day]
        diffs = {it: rev[me][day][it] - rev[op][day][it] for it in P}
        top = sorted(diffs.items(), key=lambda kv: abs(kv[1]), reverse=True)[:3]
        sp = sum(cost[me][day].values()) - sum(cost[op][day].values())
        if abs(dm) > 20 or abs(sp) > 20:
            print("%3d %8.0f %+8.0f   %-45s %+7.0f" % (day, daymargin[day], dm, " ".join("%s%+.0f" % (k[:5], v) for k, v in top if abs(v) > 5), sp))
    if a.orders:
        lo, hi = map(int, a.orders.split(":"))
        for st, b, a_, p0, p1, m0, m1, orders in log:
            if lo <= st <= hi and orders[me] != orders[op]:
                print(" step %d d%d.%02d\n   me %s\n   op %s" % (st, st // 24, st % 24, orders[me], orders[op]))


if __name__ == "__main__":
    main()

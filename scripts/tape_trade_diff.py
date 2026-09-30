#!/usr/bin/env python3
"""Per-item executed-sales difference between a candidate and replay tapes.

Plays the candidate against selected tapes exactly like
evaluate_vs_replay_tapes.py --force-money (standard kaggle runner), records
executed sales per seat and item, and prints the aggregate candidate-minus-tape
revenue by item and by phase over the selected games.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evaluate_vs_replay_tapes as E  # noqa: E402

P = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER"]


def phase(step):
    return "d0-11" if step < 288 else ("d12-19" if step < 480 else ("d20-26" if step < 648 else "d27-29"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--replays", required=True)
    ap.add_argument("--games", required=True, help="JSON [[episode, tape_seat, ...], ...]")
    a = ap.parse_args()
    import kaggle_environments.envs.kaggriculture.kaggriculture as K
    from kaggle_environments import make
    want = {(int(g[0]), int(g[1])) for g in json.load(open(a.games))}
    tapes = [t for t in E.extract_tapes(a.replays, []) if (int(t["episode"]), int(t["seat"])) in want]
    E._FORCE["enabled"] = True
    E._install_money_pin()
    cand = E.load_candidate(Path(a.candidate))
    pinned = K._process_market
    log = []

    def hooked(state, env):
        st = int(K.get(state[0].observation, "step", 0))
        b = [dict(x.observation.private.shed) for x in state]
        p0 = dict(state[0].observation.market.prices)
        r = pinned(state, env)
        af = [dict(x.observation.private.shed) for x in state]
        p1 = dict(state[0].observation.market.prices)
        log.append((st, b, af, p0, p1))
        return r

    K._process_market = hooked
    tot = Counter(); by_phase = defaultdict(Counter); margins = []
    for t in tapes:
        log.clear()
        seat = 1 - t["seat"]
        agents = [cand, E.make_tape_agent(t["actions"])] if seat == 0 else [E.make_tape_agent(t["actions"]), cand]
        E._FORCE["cfg"] = {"seat": t["seat"], "money": t["money"], "score": 3000.0}
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": t["seed"]}, debug=False)
        env.run(agents)
        margin = float(env.steps[-1][seat].reward) - E._FORCE["cfg"]["score"]
        E._FORCE["cfg"] = None
        margins.append(margin)
        g = Counter()
        for st, b, af, p0, p1 in log:
            for it in P:
                for s, sign in ((seat, 1), (t["seat"], -1)):
                    d = int(af[s].get(it, 0)) - int(b[s].get(it, 0))
                    if d < 0:
                        v = -d * (p0[it] + p1[it]) / 2 * sign
                        g[it] += v; by_phase[phase(st)][it] += v
        tot.update(g)
        print("%s seat%d %-14s margin %+6.0f  top: %s" % (t["episode"], t["seat"], t["team"][:14], margin,
              " ".join("%s%+.0f" % (k[:5], v) for k, v in sorted(g.items(), key=lambda kv: kv[1])[:3])), flush=True)
    n = max(1, len(tapes))
    print("\nmean margin %+.0f over %d games" % (sum(margins) / n, len(tapes)))
    print("mean revenue diff (candidate - tape) by item:", {k: round(v / n) for k, v in sorted(tot.items(), key=lambda kv: kv[1])})
    for ph in ("d0-11", "d12-19", "d20-26", "d27-29"):
        print("  %s" % ph, {k: round(v / n) for k, v in sorted(by_phase[ph].items(), key=lambda kv: kv[1]) if abs(v / n) > 20})


if __name__ == "__main__":
    main()

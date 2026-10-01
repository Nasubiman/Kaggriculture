#!/usr/bin/env python3
"""Teacher-force a reference agent (default results31) on public replays.

For each player in each replay, feed the recorded observations to a fresh
reference agent and compare its action with the recorded one. Reports the
opening (steps < 144) match rate, the first divergent step, the full-game
match rate, and how the market orders differ after divergence.
"""
from __future__ import annotations

import argparse
import glob
import importlib.util
import json
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF = None
MAX_DIVS = int(__import__("os").environ.get("MAX_DIVS", "6"))
MIN_DIV_STEP = int(__import__("os").environ.get("MIN_DIV_STEP", "0"))


def load_last_callable(path):
    spec = importlib.util.spec_from_file_location("ref_agent", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return [v for v in vars(module).values() if callable(v)][-1]


def units(action):
    return [action.get("farmer") or ["PASS"], *(action.get("hands") or [])]


def market(action):
    return [list(o) for o in (action.get("market") or []) if o]


def classify(args):
    path, ref_path, open_steps = args
    try:
        data = json.load(open(path))
    except (ValueError, OSError):
        return []
    steps = data["steps"]
    names = data["info"]["TeamNames"]
    config = data.get("configuration") or {}
    rows = []
    for p in (0, 1):
        agent = load_last_callable(ref_path)  # fresh module = fresh agent state
        same = same_open = n_open = 0
        first_div = None
        diff_kind = Counter()
        first_divs = []
        sell_diff = Counter()
        n = 0
        for t in range(len(steps) - 1):
            obs = dict(steps[t][p]["observation"])
            # Kaggle stores "step" only in player 0's observation.
            obs.setdefault("step", steps[t][0]["observation"].get("step", t))
            if steps[t][p].get("status") not in (None, "ACTIVE"):
                break
            actual = steps[t + 1][p].get("action") or {}
            try:
                pred = agent(obs, config) or {}
            except Exception:
                pred = {}
            match = units(pred) == units(actual) and market(pred) == market(actual)
            n += 1
            same += match
            if t < open_steps:
                n_open += 1
                same_open += match
            if not match:
                if first_div is None:
                    first_div = t
                if len(first_divs) < MAX_DIVS and t >= MIN_DIV_STEP:
                    first_divs.append({
                        "step": t,
                        "units_same": units(pred) == units(actual),
                        "pred_market": market(pred),
                        "actual_market": market(actual),
                        "pred_units": units(pred) if units(pred) != units(actual) else None,
                        "actual_units": units(actual) if units(pred) != units(actual) else None,
                        "shops": list(obs.get("town", {}).get("unlocked_shops", [])),
                        "prices": obs.get("market", {}).get("prices"),
                        "shed": (obs.get("private") or {}).get("shed"),
                    })
                if units(pred) != units(actual):
                    diff_kind["units"] += 1
                if market(pred) != market(actual):
                    diff_kind["market"] += 1
                    ps = {o[1]: o[2] for o in market(pred) if o[0] == "SELL" and len(o) > 2}
                    as_ = {o[1]: o[2] for o in market(actual) if o[0] == "SELL" and len(o) > 2}
                    for item in set(ps) | set(as_):
                        d = int(as_.get(item, 0)) - int(ps.get(item, 0))
                        if d > 0:
                            sell_diff[f"{item}:more"] += d
                        elif d < 0:
                            sell_diff[f"{item}:less"] += -d
        rows.append({
            "episode": data["info"].get("EpisodeId") or data.get("id"),
            "replay": Path(path).name,
            "player": p,
            "team": names[p],
            "opponent": names[1 - p],
            "reward": data["rewards"][p] if data.get("rewards") else None,
            "opponent_reward": data["rewards"][1 - p] if data.get("rewards") else None,
            "open_match": same_open / max(1, n_open),
            "full_match": same / max(1, n),
            "first_divergence": first_div,
            "diff_kind": dict(diff_kind),
            "sell_diff": dict(sell_diff.most_common(12)),
            "first_divs": first_divs,
        })
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--replays", required=True)
    ap.add_argument("--reference", default=str(ROOT / "agents/results31.py"))
    ap.add_argument("--open-steps", type=int, default=144)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--output", type=Path, required=True)
    a = ap.parse_args()
    files = sorted(glob.glob(a.replays))
    done = {}
    if a.output.exists():
        for r in json.load(open(a.output)):
            done.setdefault(r["replay"], []).append(r)
    todo = [f for f in files if Path(f).name not in done]
    out = [r for rs in done.values() for r in rs]
    with ProcessPoolExecutor(a.workers) as ex:
        for rows in ex.map(classify, [(f, a.reference, a.open_steps) for f in todo]):
            out.extend(rows)
            for r in rows:
                print(f"{r['replay']} p{r['player']} {r['team'][:24]:24s} open={r['open_match']:.2f} "
                      f"full={r['full_match']:.2f} div={r['first_divergence']}", flush=True)
            a.output.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    a.output.write_text(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Evaluate a candidate against recorded public players on their own seeds.

A player's farm depends only on its own actions and the episode seed; the
opponent only moves shared market prices. Replaying a recorded player's
actions on the recorded seed is therefore a close stand-in for that player.
Purchases can still fail when a changed market leaves it short of money, so
each game reports how often the tape's money diverged from the recording.
"""

from __future__ import annotations

import argparse
import glob
import json
import multiprocessing as mp
import os
import sys
from pathlib import Path
from statistics import mean
from typing import Any

from kaggle_environments.agent import get_last_callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))

_CANDIDATE_PATH = ""
_CANDIDATE: Any = None
_FAST = True
_TAPES: dict[str, Any] = {}
_FORCE: dict[str, Any] = {}


def _install_money_pin() -> None:
    """Pin the tape player's bank to its recorded balance before each market phase.

    Unit actions never spend money, so pinning right before the market phase
    lets every recorded purchase succeed. The tape's own score is rebuilt from
    the money it actually gained or lost in this simulated market.
    """
    import kaggle_environments.envs.kaggriculture.kaggriculture as K
    if getattr(K, "_tape_pin_installed", False):
        return
    original = K._process_market

    # Defaults bind the state explicitly: fast runners re-home engine functions
    # into their own globals, where this module's names are not visible.
    def pinned(state, env, _force=_FORCE, original=original, _get=K.get):
        cfg = _force.get("cfg")
        if not cfg:
            return original(state, env)
        step = int(_get(state[0].observation, "step", 0))
        seat = cfg["seat"]
        farm = state[0].observation.farms[seat]
        recorded = cfg["money"][min(step, len(cfg["money"]) - 1)]
        farm["money"] = float(recorded)
        result = original(state, env)
        cfg["score"] += float(farm["money"]) - recorded
        return result

    K._process_market = pinned
    K._tape_pin_installed = True


def load_candidate(path: Path) -> Any:
    source = path.read_text(encoding="utf-8")
    selected = get_last_callable(source, path=str(path))
    if not callable(selected):
        raise RuntimeError(f"{path} does not define a callable entry point")
    return selected


def extract_tapes(pattern: str, teams: list[str]) -> list[dict[str, Any]]:
    tapes = []
    for file in sorted(glob.glob(pattern)):
        replay = json.loads(Path(file).read_text())
        names = replay["info"]["TeamNames"]
        steps = replay["steps"]
        final = [float(s.get("reward") or 0.0) for s in steps[-1]]
        for seat, name in enumerate(names):
            if teams and name not in teams:
                continue
            actions = [step[seat].get("action") for step in steps]
            money = [float(step[seat]["observation"]["farms"][seat]["money"]) for step in steps]
            tapes.append({
                "episode": int(replay["info"]["EpisodeId"]),
                "seed": int(replay["info"]["seed"]),
                "team": name,
                "seat": seat,
                "opponent": names[1 - seat],
                "recorded_reward": final[seat],
                "recorded_opponent_reward": final[1 - seat],
                "actions": actions,
                "opponent_actions": [step[1 - seat].get("action") for step in steps],
                "money": money,
            })
    return tapes


def make_tape_agent(actions: list[Any]):
    def tape_agent(observation, configuration=None):
        step = int(observation.get("step", 0))
        if step + 1 < len(actions) and isinstance(actions[step + 1], dict):
            action = dict(actions[step + 1])
            # A desynchronised tape can address hands that were never hired;
            # the native simulator does not tolerate that, Kaggle ignores it.
            player = int(observation.get("player", 0))
            hired = len(observation["farms"][player].get("hands") or [])
            action["hands"] = list(action.get("hands") or [])[:hired]
            return action
        return {"farmer": ["PASS"], "hands": [], "market": []}
    return tape_agent


def worker_init(candidate: str, fast: bool, force_money: bool = False) -> None:
    global _CANDIDATE_PATH, _CANDIDATE, _FAST
    _CANDIDATE_PATH = candidate
    _CANDIDATE = None
    _FAST = fast and not force_money
    _FORCE["enabled"] = force_money
    if force_money:
        _install_money_pin()


_CANDIDATES: dict[str, Any] = {}


def play_multi(task):
    """(candidate_path, tape) task for the single-pool multi-candidate mode."""
    global _CANDIDATE, _CANDIDATE_PATH
    path, tape = task
    if path not in _CANDIDATES:
        _CANDIDATES[path] = load_candidate(Path(path))
    _CANDIDATE_PATH, _CANDIDATE = path, _CANDIDATES[path]
    row = play(tape)
    row["candidate"] = Path(path).stem
    return row


def play(tape: dict[str, Any]) -> dict[str, Any]:
    global _CANDIDATE
    try:
        if str(_CANDIDATE_PATH).endswith("RECORDED"):
            # Validation mode: the recorded opponent replays itself.
            _CANDIDATE = make_tape_agent(tape["opponent_actions"])
        elif _CANDIDATE is None:
            _CANDIDATE = load_candidate(Path(_CANDIDATE_PATH))
        seat = 1 - tape["seat"]
        tape_agent = make_tape_agent(tape["actions"])
        agents = [_CANDIDATE, tape_agent] if seat == 0 else [tape_agent, _CANDIDATE]
        if _FORCE.get("enabled"):
            _FORCE["cfg"] = {"seat": tape["seat"], "money": tape["money"], "score": 3000.0}
        if _FORCE.get("enabled"):
            # Pure-Python fast runner: it calls the official market phase, so the
            # money pin applies, and it matches the standard runner exactly.
            from fast_kaggriculture import run_fast_episode as run_python_fast
            final = run_python_fast(agents, seed=tape["seed"])
        elif _FAST:
            from production_fast_kaggriculture import run_fast_episode
            final = run_fast_episode(agents, seed=tape["seed"])
        else:
            from kaggle_environments import make
            env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": tape["seed"]}, debug=False)
            env.run(agents)
            final = env.steps[-1]
        reward = float(final[seat].reward)
        tape_reward = float(final[tape["seat"]].reward)
        if _FORCE.get("enabled"):
            tape_reward = _FORCE["cfg"]["score"]
            _FORCE["cfg"] = None
        return {
            "episode": tape["episode"], "seed": tape["seed"], "team": tape["team"],
            "tape_seat": tape["seat"], "recorded_opponent": tape["opponent"],
            "reward": reward, "tape_reward": tape_reward, "margin": reward - tape_reward,
            "win": reward > tape_reward,
            "recorded_reward": tape["recorded_reward"],
            "recorded_opponent_reward": tape["recorded_opponent_reward"],
            "error": None,
        }
    except Exception as error:  # keep the batch alive, report the failure
        return {"episode": tape["episode"], "team": tape["team"], "error": repr(error),
                "reward": 0.0, "tape_reward": 0.0, "margin": 0.0, "win": False}


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ok = [r for r in rows if r["error"] is None]
    if not ok:
        return {"games": len(rows), "errors": len(rows)}
    return {
        "games": len(rows),
        "wins": sum(r["win"] for r in ok),
        "win_rate": mean(float(r["win"]) for r in ok),
        "mean_reward": mean(r["reward"] for r in ok),
        "mean_tape_reward": mean(r["tape_reward"] for r in ok),
        "mean_margin": mean(r["margin"] for r in ok),
        "mean_recorded_tape_reward": mean(r["recorded_reward"] for r in ok),
        "mean_recorded_margin_of_tape": mean(r["recorded_reward"] - r["recorded_opponent_reward"] for r in ok),
        "errors": len(rows) - len(ok),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, default=ROOT / "main.py")
    parser.add_argument("--replays", default=str(ROOT / "replays/public_20260925_4q_named/episode-*-replay.json"))
    parser.add_argument("--teams", nargs="*", default=[])
    parser.add_argument("--exclude-teams", nargs="*", default=[],
                        help="omit these teams when extracting or reading tapes")
    parser.add_argument("--tapes-file", type=Path, default=None,
                        help="gzip JSON of extracted tapes (read, or written with --export)")
    parser.add_argument("--export", action="store_true", help="only write --tapes-file and exit")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--fast-runner", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--force-money", action="store_true",
                        help="pin the tape bank to its recording so every recorded purchase succeeds")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--candidates", nargs="*", default=[],
                        help="multi-candidate mode: one pool over every (candidate, tape); writes --output-dir/<stem>.json")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--base-results", type=Path, default=None,
                        help="keep only tapes this earlier run lost or won by less than --max-abs-margin")
    parser.add_argument("--max-abs-margin", type=float, default=1500.0)
    args = parser.parse_args()

    import gzip
    if args.tapes_file and args.tapes_file.exists() and not args.export:
        tapes = json.loads(gzip.decompress(args.tapes_file.read_bytes()))
        if args.teams:
            tapes = [t for t in tapes if t["team"] in args.teams]
    else:
        tapes = extract_tapes(args.replays, args.teams)
    if args.exclude_teams:
        tapes = [t for t in tapes if t["team"] not in args.exclude_teams]
    if args.export:
        args.tapes_file.parent.mkdir(parents=True, exist_ok=True)
        args.tapes_file.write_bytes(gzip.compress(json.dumps(tapes).encode()))
        print(f"wrote {len(tapes)} tapes to {args.tapes_file}")
        return
    if args.limit:
        tapes = tapes[: args.limit]
    if args.base_results:
        base = json.loads(args.base_results.read_text())["games"]
        keep = {(g["episode"], g["team"]) for g in base
                if not g.get("error") and (not g["win"] or abs(g["margin"]) < args.max_abs_margin)}
        tapes = [t for t in tapes if (t["episode"], t["team"]) in keep]
        print(f"decisive tapes: {len(tapes)}", flush=True)
    if args.candidates:
        ctx = mp.get_context("spawn")
        tasks = [(str(Path(c).resolve()), t) for c in args.candidates for t in tapes]
        with ctx.Pool(max(1, min(args.workers, os.cpu_count() or 1)), initializer=worker_init,
                      initargs=("", args.fast_runner, args.force_money)) as pool:
            rows = list(pool.imap_unordered(play_multi, tasks, chunksize=1))
        args.output_dir.mkdir(parents=True, exist_ok=True)
        for c in args.candidates:
            stem = Path(c).stem
            mine = [r for r in rows if r.get("candidate") == stem]
            (args.output_dir / f"{stem}.json").write_text(json.dumps({"candidate": c, "overall": summarize(mine), "games": mine}))
            print(stem, summarize(mine), flush=True)
        return
    ctx = mp.get_context("spawn")
    with ctx.Pool(max(1, min(args.workers, os.cpu_count() or 1)), initializer=worker_init,
                  initargs=(str(args.candidate.resolve()), args.fast_runner, args.force_money)) as pool:
        rows = list(pool.imap_unordered(play, tapes, chunksize=1))
    rows.sort(key=lambda r: (r["team"], r["episode"]))
    teams = sorted({r["team"] for r in rows})
    by_team = {t: summarize([r for r in rows if r["team"] == t]) for t in teams}
    overall = summarize(rows)
    result = {"candidate": str(args.candidate.resolve()), "overall": overall,
              "by_team": by_team, "games": rows}
    print(json.dumps({"overall": overall}, indent=1))
    for t in sorted(by_team, key=lambda t: -by_team[t]["games"])[:12]:
        s = by_team[t]
        print(f"{t[:28]:28s} n={s['games']:3d} win={s.get('win_rate',0):.2f} "
              f"margin={s.get('mean_margin',0):+8.0f} me={s.get('mean_reward',0):8.0f} "
              f"tape={s.get('mean_tape_reward',0):8.0f} rec_tape={s.get('mean_recorded_tape_reward',0):8.0f}")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result))


if __name__ == "__main__":
    main()

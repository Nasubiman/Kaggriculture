#!/usr/bin/env python3
"""Build compressed deterministic agents from representative rank-1 trajectories."""

from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
import zlib


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--quantiles", default="0.1,0.25,0.5,0.75,0.9")
    parser.add_argument("--all", action="store_true", help="Write one candidate for every public game")
    args = parser.parse_args()
    manifest = json.loads((args.replay_dir/"manifest.json").read_text()); team = manifest["teams"][0]["team_name"]
    games = []
    for episode in manifest["teams"][0]["episodes"]:
        replay = json.loads((args.replay_dir/episode["replay"]).read_text()); seat = replay["info"]["TeamNames"].index(team)
        rewards = [float(state.get("reward") or 0) for state in replay["steps"][-1]]
        actions = [replay["steps"][step+1][seat].get("action") or {"farmer":["PASS"],"hands":[],"market":[]}
                   for step in range(len(replay["steps"])-1)]
        games.append((rewards[seat], rewards[seat]-rewards[1-seat], int(replay["info"]["EpisodeId"]), seat, actions))
    games.sort(); args.output_dir.mkdir(parents=True, exist_ok=True)
    selections = ([(index/(len(games)-1), value) for index, value in enumerate(games)] if args.all else
                  [(fraction, games[round((len(games)-1)*fraction)]) for fraction in map(float, args.quantiles.split(","))])
    for fraction, (reward, margin, episode, seat, actions) in selections:
        encoded = base64.b85encode(zlib.compress(json.dumps(actions,separators=(",", ":")).encode(), 9)).decode()
        name = (f"episode{episode}" if args.all else f"q{round(fraction*100):02d}_episode{episode}")
        target = args.output_dir/name; target.mkdir(parents=True, exist_ok=True)
        source = f'''"""Rank-1 public trajectory tape; episode {episode}, reward {reward:.0f}."""\nimport base64,copy,json,zlib\n_DATA={encoded!r}\n_TAPE=json.loads(zlib.decompress(base64.b85decode(_DATA)).decode())\ndef agent(observation,configuration=None):\n step=int(observation.get("step",0))\n return copy.deepcopy(_TAPE[step]) if step<len(_TAPE) else {{"farmer":["PASS"],"hands":[],"market":[]}}\n'''
        (target/"main.py").write_text(source)
        (target/"metadata.json").write_text(json.dumps({"episode":episode,"seat":seat,"reward":reward,"margin":margin,"quantile":fraction},indent=2)+"\n")
        print(name, f"reward={reward:.0f}", f"margin={margin:+.0f}", f"compressed={len(encoded)}")


if __name__ == "__main__": main()

#!/usr/bin/env python3
"""Convert public replays into compact full-observation imitation examples."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    manifest = json.loads((args.replay_dir / "manifest.json").read_text())
    team_info = manifest["teams"][0]
    team = team_info["team_name"]
    episodes = team_info["episodes"]
    rows = 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(args.output, "wt", encoding="utf-8", compresslevel=6) as target:
        header = {
            "type": "metadata", "schema": 1, "team": team,
            "submission_id": team_info["submission_id"], "games": len(episodes),
        }
        target.write(json.dumps(header, separators=(",", ":")) + "\n")
        for index, episode in enumerate(episodes, start=1):
            replay = json.loads((args.replay_dir / episode["replay"]).read_text())
            names = replay["info"]["TeamNames"]
            seat = names.index(team)
            # Kaggle's serialized action in steps[t+1] was selected from the
            # observation in steps[t].  The step-0 action is a placeholder.
            for step in range(len(replay["steps"]) - 1):
                state = replay["steps"][step][seat]
                next_state = replay["steps"][step + 1][seat]
                observation = state.get("observation") or {}
                if len(observation.get("farms", []) or []) < 2:
                    continue
                example = {
                    "type": "example", "episode": int(replay["info"]["EpisodeId"]),
                    "step": step, "seat": seat, "opponent": names[1-seat],
                    "observation": observation,
                    "action": next_state.get("action") or {"farmer": ["PASS"], "hands": [], "market": []},
                }
                target.write(json.dumps(example, separators=(",", ":")) + "\n")
                rows += 1
            if index % 25 == 0:
                print(f"processed {index}/{len(episodes)}", flush=True)
    print(f"wrote {args.output}: {rows} examples")


if __name__ == "__main__":
    main()

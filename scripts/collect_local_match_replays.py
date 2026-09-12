#!/usr/bin/env python3
"""Run official-engine matches and save them in public-replay-compatible form."""

from __future__ import annotations

import argparse
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from kaggle_environments import make


ROOT = Path(__file__).resolve().parents[1]


def load_agent(path: Path, module_name: str) -> Any:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.agent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, default=ROOT / "main.py")
    parser.add_argument("--opponent", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed-start", type=int, default=11_000_000)
    parser.add_argument("--seeds", type=int, default=5)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    episodes = []
    for index in range(args.seeds):
        seed = args.seed_start + 17 * index
        seat = index % 2
        candidate = load_agent(args.candidate.resolve(), f"candidate_{seed}")
        opponent = load_agent(args.opponent.resolve(), f"opponent_{seed}")
        agents = [candidate, opponent] if seat == 0 else [opponent, candidate]
        names = ["candidate", "opponent"] if seat == 0 else ["opponent", "candidate"]
        environment = make(
            "kaggriculture",
            configuration={"episodeSteps": 720, "seed": seed},
            debug=False,
        )
        environment.run(agents)
        replay = environment.toJSON()
        replay["info"] = dict(replay.get("info") or {})
        replay["info"].update(TeamNames=names, EpisodeId=seed, seed=seed)
        replay["rewards"] = [float(state.reward) for state in environment.steps[-1]]
        filename = f"episode-{seed}-replay.json"
        (args.output_dir / filename).write_text(json.dumps(replay) + "\n", encoding="utf-8")
        episodes.append({"episode_id": seed, "created_at": None, "replay": filename})
        print(f"{index + 1}/{args.seeds} seed={seed} seat={seat} rewards={replay['rewards']}", flush=True)
    manifest = {
        "competition": "kaggriculture",
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "top_teams": 1,
        "episodes_per_team": args.seeds,
        "teams": [{
            "rank": 1,
            "team_id": -1,
            "team_name": "candidate",
            "leaderboard_score": None,
            "submission_id": -1,
            "submission_score": None,
            "episodes": episodes,
        }],
    }
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.output_dir / 'manifest.json'}")


if __name__ == "__main__":
    main()

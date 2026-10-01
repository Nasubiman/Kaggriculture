#!/usr/bin/env python3
"""Evaluate an agent file over fixed seeds and both player positions.

Like evaluate_agent.py, but loads the file the way Kaggle does (its last
callable), so wrapper layers appended to a candidate are the ones evaluated.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from statistics import mean, pstdev

from kaggle_environments import make


ROOT = Path(__file__).resolve().parents[1]


def load_agent(path: Path):
    spec = importlib.util.spec_from_file_location("candidate_agent", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return [v for v in vars(module).values() if callable(v)][-1]  # Kaggle semantics: last callable


def evaluate(agent_path: Path, opponents: list[str], seeds: list[int]) -> dict:
    candidate = load_agent(agent_path)
    games = []
    for opponent in opponents:
        for seed in seeds:
            for seat in (0, 1):
                agents = [candidate, opponent] if seat == 0 else [opponent, candidate]
                env = make(
                    "kaggriculture",
                    configuration={"episodeSteps": 720, "seed": seed},
                    debug=True,
                )
                env.run(agents)
                final = env.steps[-1]
                reward = float(final[seat].reward)
                opponent_reward = float(final[1 - seat].reward)
                game = {
                    "opponent": opponent,
                    "seed": seed,
                    "seat": seat,
                    "reward": reward,
                    "opponent_reward": opponent_reward,
                    "margin": reward - opponent_reward,
                    "win": reward > opponent_reward,
                    "status": final[seat].status,
                }
                games.append(game)
                print(
                    f"{opponent} seed={seed} seat={seat}: "
                    f"{reward:.0f} vs {opponent_reward:.0f} ({final[seat].status})"
                )

    return {
        "agent": str(agent_path),
        "games": games,
        "summary": {
            "games": len(games),
            "win_rate": mean(float(game["win"]) for game in games),
            "mean_reward": mean(game["reward"] for game in games),
            "reward_stddev": pstdev(game["reward"] for game in games),
            "mean_margin": mean(game["margin"] for game in games),
            "all_done": all(game["status"] == "DONE" for game in games),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", type=Path, default=ROOT / "submissions" / "ahd27s2.py")
    parser.add_argument("--opponents", nargs="+", default=["starter", "random"])
    parser.add_argument("--seeds", nargs="+", type=int, default=[101, 202, 303])
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "evaluate_agent_lc.json")
    args = parser.parse_args()

    result = evaluate(args.agent.resolve(), args.opponents, args.seeds)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2))
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()

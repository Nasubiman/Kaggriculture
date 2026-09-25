#!/usr/bin/env python3
"""Compare local policy implementations against aligned public teacher actions."""

from __future__ import annotations

import argparse
from collections import defaultdict
import importlib.util
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def load_agent(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None: raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    selected = getattr(module, "kaggle_agent", None) or getattr(module, "agent", None)
    if not callable(selected): raise RuntimeError(f"no agent in {path}")
    return selected


def command_accuracy(predicted: dict[str, Any], actual: dict[str, Any]) -> tuple[int, int]:
    p = [predicted.get("farmer") or ["PASS"], *(predicted.get("hands") or [])]
    a = [actual.get("farmer") or ["PASS"], *(actual.get("hands") or [])]
    total = max(len(a), len(p)); p += [["<MISSING>"]] * (total-len(p)); a += [["<MISSING>"]] * (total-len(a))
    return sum(x == y for x, y in zip(p, a)), total


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay-dir", type=Path, required=True)
    parser.add_argument("--manifest-name", default="manifest.json")
    parser.add_argument("--games", type=int, default=5)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--models", nargs="*")
    args = parser.parse_args()
    manifest = json.loads((args.replay_dir/args.manifest_name).read_text()); teacher = manifest["teams"][0]["team_name"]
    paths = {"current_main": ROOT/"main.py"}
    for path in sorted((ROOT/"test").glob("*/main.py")): paths[path.parent.name] = path
    if args.models: paths = {name: paths[name] for name in args.models}
    metrics = {name: defaultdict(int) for name in paths}
    for game_index, episode in enumerate(manifest["teams"][0]["episodes"][:args.games]):
        replay = json.loads((args.replay_dir/episode["replay"]).read_text()); seat = replay["info"]["TeamNames"].index(teacher)
        for model_index, (name, path) in enumerate(paths.items()):
            policy = load_agent(path.resolve(), f"teacher_forced_{model_index}_{game_index}")
            row = metrics[name]
            for step in range(len(replay["steps"])-1):
                obs = replay["steps"][step][seat]["observation"]
                actual = replay["steps"][step+1][seat].get("action") or {"farmer":["PASS"],"hands":[],"market":[]}
                try: predicted = policy(obs)
                except Exception:
                    row["errors"] += 1; predicted = {"farmer":["PASS"],"hands":[],"market":[]}
                row["turns"] += 1; row["exact"] += predicted == actual
                row["market"] += (predicted.get("market") or []) == (actual.get("market") or [])
                good, total = command_accuracy(predicted, actual); row["actor_good"] += good; row["actor_total"] += total
                if step < 24: row["opening_exact"] += predicted == actual; row["opening_turns"] += 1
            print(f"game {game_index+1}/{min(args.games, len(manifest['teams'][0]['episodes']))} {name}", flush=True)
    result = []
    for name, row in metrics.items():
        result.append({"model":name, "path":str(paths[name]), "turns":row["turns"], "errors":row["errors"],
                       "exact_turn":row["exact"]/row["turns"], "market_exact":row["market"]/row["turns"],
                       "actor_command":row["actor_good"]/row["actor_total"],
                       "opening_exact":row["opening_exact"]/row["opening_turns"]})
    result.sort(key=lambda x:(x["exact_turn"], x["actor_command"]), reverse=True)
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(result,indent=2)+"\n")
    for row in result: print(f"{row['model']}: exact={row['exact_turn']:.2%} actor={row['actor_command']:.2%} market={row['market_exact']:.2%} opening={row['opening_exact']:.2%}")


if __name__ == "__main__": main()

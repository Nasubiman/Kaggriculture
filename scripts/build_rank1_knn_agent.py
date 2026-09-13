#!/usr/bin/env python3
"""Build a state-conditioned nearest-neighbor agent from rank-1 replays."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
import zlib

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "training"))
from rank1_knn_runtime import encode  # noqa: E402


def feature_weights(size: int) -> np.ndarray:
    """Return hand-tuned weights for the stable role-aware state encoding."""
    if size != 879:
        raise ValueError(f"unexpected feature size {size}; update offsets and weights")
    weights = np.ones(size, dtype=np.uint8)
    # Tile type (0:100) is scored as a categorical mismatch in the runtime.
    weights[200:300] = 8       # watered/fed/cared/fertilizer flags
    weights[300:400] = 5       # neglected days
    weights[500:532] = 10      # farmer and hand positions
    weights[532:676] = 3       # carried goods per actor
    weights[676:679] = (2, 12, 12)  # money, hand count, hires today
    weights[679:688] = 4       # shed
    weights[688:693] = 4       # seeds
    weights[693:702] = 2       # market prices
    weights[702:711] = 2       # market inventory
    weights[711:719] = 15      # unlocked shops
    weights[719:732] = 3       # opponent board composition
    weights[732:734] = (1, 5)  # opponent money and hands
    weights[734:750] = 1       # actor-local tile code; categorical correction is in runtime
    weights[750:878] = 18      # eight available-task flags for each actor
    weights[878] = 50          # seat: never imitate the other orientation by accident
    return weights


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--switch-interval", type=int, default=1)
    parser.add_argument("--switch-penalty", type=int, default=0)
    parser.add_argument("--actor-repair", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument(
        "--runtime",
        type=Path,
        default=ROOT / "training" / "rank1_knn_runtime.py",
    )
    args = parser.parse_args()

    manifest = json.loads((args.replay_dir / "manifest.json").read_text())
    team = manifest["teams"][0]["team_name"]
    episodes = manifest["teams"][0]["episodes"]
    encoded_games: list[np.ndarray] = []
    action_tapes: list[list[dict]] = []
    metadata: list[dict] = []

    for index, episode in enumerate(episodes, 1):
        replay = json.loads((args.replay_dir / episode["replay"]).read_text())
        seat = replay["info"]["TeamNames"].index(team)
        usable_steps = min(719, len(replay["steps"]) - 1)
        if usable_steps != 719:
            print(f"skip episode {episode['episode_id']}: only {usable_steps} actions")
            continue
        features = np.stack(
            [encode(replay["steps"][step][seat]["observation"]) for step in range(719)]
        ).astype(np.uint8)
        actions = [
            replay["steps"][step + 1][seat].get("action")
            or {"farmer": ["PASS"], "hands": [], "market": []}
            for step in range(719)
        ]
        rewards = [float(state.get("reward") or 0) for state in replay["steps"][-1]]
        encoded_games.append(features)
        action_tapes.append(actions)
        metadata.append(
            {
                "episode_id": int(replay["info"]["EpisodeId"]),
                "seat": seat,
                "reward": rewards[seat],
                "margin": rewards[seat] - rewards[1 - seat],
            }
        )
        if index % 25 == 0 or index == len(episodes):
            print(f"loaded {index}/{len(episodes)} replays")

    # Stack as [step, replay, feature] so inference reads one contiguous step slab.
    library = np.stack(encoded_games, axis=1)
    weights = feature_weights(library.shape[-1])
    args.output_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.output_dir / "library.npz", features=library, weights=weights)
    (args.output_dir / "actions.zlib").write_bytes(
        zlib.compress(json.dumps(action_tapes, separators=(",", ":")).encode(), 9)
    )
    shutil.copyfile(args.runtime, args.output_dir / "main.py")
    (args.output_dir / "settings.json").write_text(
        json.dumps(
            {
                "switch_interval": max(1, args.switch_interval),
                "switch_penalty": max(0, args.switch_penalty),
                "actor_repair": args.actor_repair,
            },
            indent=2,
        )
        + "\n"
    )
    (args.output_dir / "metadata.json").write_text(
        json.dumps(
            {
                "source": str(args.replay_dir),
                "team": team,
                "games": len(encoded_games),
                "steps": int(library.shape[0]),
                "feature_size": int(library.shape[2]),
                "episodes": metadata,
            },
            indent=2,
        )
        + "\n"
    )
    print(f"wrote {args.output_dir}: features={library.shape}")


if __name__ == "__main__":
    main()

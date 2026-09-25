#!/usr/bin/env python3
"""Split one public submission's replays by seed before imitation training.

Repeated episodes with the same game seed always stay in the same partition.
The output files retain the collector's manifest schema and can be passed to
the existing imitation-dataset and nearest-trajectory builders.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay-dir", type=Path, required=True)
    parser.add_argument("--manifest-name", default="manifest.json")
    parser.add_argument("--validation-fraction", type=float, default=0.2)
    parser.add_argument("--prefix", default="imitation")
    args = parser.parse_args()
    if not 0 < args.validation_fraction < 1:
        parser.error("validation-fraction must be between 0 and 1")
    manifest = json.loads((args.replay_dir / args.manifest_name).read_text())
    if len(manifest["teams"]) != 1:
        parser.error("manifest must contain exactly one teacher team")
    episodes = manifest["teams"][0]["episodes"]
    groups = {"train": [], "validation": []}
    seen: set[int] = set()
    skipped: list[int] = []
    for episode in episodes:
        episode_id = int(episode["episode_id"])
        if episode_id in seen:
            continue
        seen.add(episode_id)
        path = args.replay_dir / episode["replay"]
        if not path.is_file():
            raise SystemExit(f"missing replay: {path}")
        replay = json.loads(path.read_text(encoding="utf-8"))
        if len(replay.get("steps") or []) < 720:
            skipped.append(episode_id)
            continue
        seed = int(replay["info"]["seed"])
        digest = hashlib.sha256(str(seed).encode("ascii")).digest()
        value = int.from_bytes(digest[:8], "big") / 2**64
        partition = "validation" if value < args.validation_fraction else "train"
        groups[partition].append(episode)
    if not groups["train"] or not groups["validation"]:
        raise SystemExit("empty partition; adjust validation-fraction")
    for partition, items in groups.items():
        split_manifest = dict(manifest)
        split_manifest["teams"] = [dict(manifest["teams"][0], episodes=items)]
        split_manifest["split"] = {
            "method": "sha256(game_seed)",
            "partition": partition,
            "validation_fraction": args.validation_fraction,
            "source_manifest": args.manifest_name,
            "skipped_incomplete_episodes": skipped,
        }
        output = args.replay_dir / f"{args.prefix}_{partition}_manifest.json"
        output.write_text(json.dumps(split_manifest, indent=2) + "\n", encoding="utf-8")
        print(f"{output}: {len(items)} episodes")


if __name__ == "__main__":
    main()

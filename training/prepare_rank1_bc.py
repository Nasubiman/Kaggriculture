#!/usr/bin/env python3
"""Precompute tensor files and exact command vocabularies for rank-1 BC."""

from __future__ import annotations

import argparse
from collections import Counter
import gzip
import json
from pathlib import Path

import numpy as np
from numpy.lib.format import open_memmap

from rank1_bc_model import (
    MAX_ACTORS, MAX_MARKET_ORDERS, canonical_command, encode_observation,
)


def examples(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as source:
        for line in source:
            row = json.loads(line)
            if row.get("type") == "example":
                yield row


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    actor_counts: Counter[str] = Counter(); market_counts: Counter[str] = Counter(); rows = 0
    for row in examples(args.dataset):
        action = row["action"]
        for command in [action.get("farmer"), *(action.get("hands", []) or [])]:
            actor_counts[canonical_command(command)] += 1
        for command in action.get("market", []) or []:
            market_counts[canonical_command(command)] += 1
        rows += 1
        if rows % 25000 == 0: print(f"vocabulary pass {rows}", flush=True)
    actor_vocab = [name for name, _ in actor_counts.most_common()]
    market_vocab = ["<PAD>", *(name for name, _ in market_counts.most_common())]
    actor_index = {name: index for index, name in enumerate(actor_vocab)}
    market_index = {name: index for index, name in enumerate(market_vocab)}

    first = next(examples(args.dataset)); state, actors, _ = encode_observation(first["observation"])
    args.output_dir.mkdir(parents=True, exist_ok=True)
    states = open_memmap(args.output_dir/"states.npy", mode="w+", dtype=np.float16,
                         shape=(rows, len(state)))
    actor_features = open_memmap(args.output_dir/"actors.npy", mode="w+", dtype=np.float16,
                                 shape=(rows, MAX_ACTORS, actors.shape[-1]))
    actor_targets = open_memmap(args.output_dir/"actor_targets.npy", mode="w+", dtype=np.int16,
                                shape=(rows, MAX_ACTORS)); actor_targets[:] = -1
    market_targets = open_memmap(args.output_dir/"market_targets.npy", mode="w+", dtype=np.int16,
                                 shape=(rows, MAX_MARKET_ORDERS)); market_targets[:] = 0
    episodes = open_memmap(args.output_dir/"episodes.npy", mode="w+", dtype=np.int64, shape=(rows,))

    for index, row in enumerate(examples(args.dataset)):
        state, actor_feature, actor_mask = encode_observation(row["observation"])
        states[index] = state; actor_features[index] = actor_feature; episodes[index] = int(row["episode"])
        action = row["action"]
        commands = [action.get("farmer"), *(action.get("hands", []) or [])]
        for actor, command in enumerate(commands[:MAX_ACTORS]):
            actor_targets[index, actor] = actor_index[canonical_command(command)]
        for slot, command in enumerate((action.get("market", []) or [])[:MAX_MARKET_ORDERS]):
            market_targets[index, slot] = market_index[canonical_command(command)]
        if (index + 1) % 10000 == 0: print(f"encoded {index+1}/{rows}", flush=True)
    for array in (states, actor_features, actor_targets, market_targets, episodes): array.flush()
    metadata = {
        "schema": 1, "source": str(args.dataset), "rows": rows,
        "state_size": len(state), "actor_feature_size": actors.shape[-1],
        "actor_vocab": actor_vocab, "market_vocab": market_vocab,
        "actor_counts": dict(actor_counts), "market_counts": dict(market_counts),
        "validation_rule": "episode_id % 5 == 0",
    }
    (args.output_dir/"metadata.json").write_text(json.dumps(metadata, indent=2)+"\n")
    print(f"wrote {args.output_dir}: rows={rows} state={len(state)} actor_vocab={len(actor_vocab)} market_vocab={len(market_vocab)}")


if __name__ == "__main__":
    main()
